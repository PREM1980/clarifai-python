import copy
import json
import logging

from pprint import pformat
import requests

from clarifai.errors import ApiError
from clarifai.versions import CLIENT_VERSION, OS_VER, PYTHON_VERSION

logger = logging.getLogger('clarifai')


class HttpClient:

  def __init__(self, api_key):
    self._api_key = api_key

  def execute_request(self, method, params, url):
    headers = {
        'Content-Type': 'application/json',
        'X-Clarifai-Client': 'python:%s' % CLIENT_VERSION,
        'Python-Client': '%s:%s' % (OS_VER, PYTHON_VERSION),
        'Authorization': 'Key %s' % self._api_key
    }
    logger.debug("=" * 100)
    succinct_payload = self._mangle_base64_values(params)
    logger.debug("%s %s\nHEADERS:\n%s\nPAYLOAD:\n%s", method, url, pformat(headers),
                 pformat(succinct_payload))
    try:
      if method == 'GET':
        res = requests.get(url, params=params, headers=headers)
      elif method == "POST":
        res = requests.post(url, data=json.dumps(params), headers=headers)
      elif method == "DELETE":
        res = requests.delete(url, data=json.dumps(params), headers=headers)
      elif method == "PATCH":
        res = requests.patch(url, data=json.dumps(params), headers=headers)
      elif method == "PUT":
        res = requests.put(url, data=json.dumps(params), headers=headers)
      else:
        raise Exception("Unsupported request type: '%s'" % method)
    except requests.RequestException as e:
      raise ApiError(url, params, method, e.response)
    try:
      response_json = json.loads(res.content.decode('utf-8'))
    except ValueError:
      logger.exception("Could not get valid JSON from server response.")
      logger.debug("\nRESULT:\n%s", pformat(res.content.decode('utf-8')))
      error = ApiError(url, params, method, res)
      raise error
    else:
      logger.debug("\nRESULT:\n%s", pformat(response_json))
    if int(res.status_code / 100) != 2:
      error = ApiError(url, params, method, res)
      logger.warn("%s", str(error))
      raise error
    return response_json

  def _mangle_base64_values(self, params):
    """ Mangle (shorten) the base64 values because they are too long for output. """
    inputs = (params or {}).get('inputs')
    query = (params or {}).get('query')
    if inputs and len(inputs) > 0:
      return self._mangle_base64_values_in_inputs(params)
    if query and query.get('ands'):
      return self._mangle_base64_values_in_query(params)
    return params

  def _mangle_base64_values_in_inputs(self, params):
    params_copy = copy.deepcopy(params)
    for data in params_copy['inputs']:
      data = data['data']
      image = data.get('image')
      if image and image.get('base64'):
        image['base64'] = self._shortened_base64_value(image['base64'])

      video = data.get('video')
      if video and video.get('base64'):
        video['base64'] = self._shortened_base64_value(video['base64'])
    return params_copy

  def _mangle_base64_values_in_query(self, params):
    params_copy = copy.deepcopy(params)
    queries = params_copy['query']['ands']
    for query in queries:
      image = query.get('output', {}).get('input', {}).get('data', {}).get('image', {})
      base64_val = image.get('base64')
      if base64_val:
        image['base64'] = self._shortened_base64_value(base64_val)
    return params_copy

  def _shortened_base64_value(self, original_base64):
    # Shorten the value if larger than what we shorten to (10 + 6 + 10).
    if len(original_base64) > 36:
      return original_base64[:10] + '......' + original_base64[-10:]
    else:
      return original_base64
