import sys
import datetime
import os
import urllib
import argparse

import requests
import pandas
import fbprophet
import prometheus_client

parser = argparse.ArgumentParser()
parser.add_argument('name', type=str)
parser.add_argument('query', type=str)
parser.add_argument('start', type=str)
parser.add_argument('end', type=str)
parser.add_argument('--frequency', type=str, default='hours', choices=['1minutes', '5minutes', '10minutes', 'hours', 'days'])
parser.add_argument('--periods', type=int, default=1)
parser.add_argument('--changepoint_range', type=float, default=0.8)
parser.add_argument('--changepoint_prior_scale', type=float, default=0.05)
parser.add_argument('--n_changepoints', type=int, default=25)
parser.add_argument('--seasonality_mode', type=str, default='additive', choices=['additive', 'multiplicative'])
parser.add_argument('--seasonality_prior_scale', type=float, default=10.0)
args = parser.parse_args()

PROMETHEUS_HOST = os.environ.get('PROMETHEUS_HOST')
PUSHGATEWAY_HOST = os.environ.get('PUSHGATEWAY_HOST')
IGNORE_KEYS = ['__name__']

step = ''
freq = ''
if args.frequency == '1minutes':
  step = '60s'
  freq = '1min'
elif args.frequency == '5minutes':
  step = '300s'
  freq = '5min'
elif args.frequency == '10minutes':
  step = '600s'
  freq = '10min'
elif args.frequency == 'hours':
  step = '3600s'
  freq = 'H'
elif args.frequency == 'days':
  step = '86400s'
  freq = 'D'

if PROMETHEUS_HOST is None or PUSHGATEWAY_HOST is None:
  print('PROMETHEUS_HOST, PUSHGATEWAY_HOST are required', file=sys.stderr)
  sys.exit(1)

response = requests.get(PROMETHEUS_HOST + '/api/v1/query_range?query=' + urllib.parse.quote(args.query) + "&start=" + args.start + "&end=" + args.end + "&step=" + step)
json = response.json()
if json['status'] == 'error':
  print(json['error'], file=sys.stderr)
  sys.exit(1)

result = json['data']['result']

gauge_map = {}
registry = prometheus_client.CollectorRegistry()

for r in result:
  labels = []
  values = []

  for k, v in r['metric'].items():
    if k not in IGNORE_KEYS:
      labels.append(k)
      values.append(v)

  if len(r['values']) < 2:
    continue

  df = pandas.DataFrame([[datetime.datetime.fromtimestamp(value[0]), value[1]] for value in r['values']])
  df.columns = ['ds', 'y']
  p = fbprophet.Prophet(changepoint_range=args.changepoint_range,changepoint_prior_scale=args.changepoint_prior_scale,n_changepoints=args.n_changepoints,seasonality_mode=args.seasonality_mode,seasonality_prior_scale=args.seasonality_prior_scale)
  p.fit(df)
  forecast = p.predict(p.make_future_dataframe(periods=args.periods, freq=freq))

  for i, row in forecast.tail(args.periods).iterrows():
    name = args.name + ':prediction'
    gauge_map[name] = gauge_map.get(name) or prometheus_client.Gauge(name, '', ['predicted_' + l for l in labels] + ['periods', 'frequency'], registry=registry)
    gauge_map[name].labels(*values, *[str(args.periods - (len(forecast) - i) + 1), args.frequency]).set(row['yhat'])

prometheus_client.pushadd_to_gateway(PUSHGATEWAY_HOST, job='promphet', grouping_key={'query': args.query + ':' + args.frequency}, registry=registry)
