import json
import sys

with open('dist-config.json') as f:
    data = json.load(f)

config = data['DistributionConfig']
etag = data['ETag']

# 1. Fix Origin Protocol Policy
config['Origins']['Items'][0]['CustomOriginConfig']['OriginProtocolPolicy'] = 'https-only'

# 2. Fix Query String Forwarding
if 'ForwardedValues' in config['DefaultCacheBehavior']:
    config['DefaultCacheBehavior']['ForwardedValues']['QueryString'] = True

# 3. Save clean config for AWS CLI
with open('update-config.json', 'w') as f:
    json.dump(config, f)

# Output ETag for shell usage
print(etag)
