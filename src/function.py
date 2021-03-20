import json
from calendar import monthrange

import arrow
import requests
import time
from dateutil.relativedelta import relativedelta


def main(args):
    print('Inside function.py, args', args)
    parameters = args.get('_parameters')
    print('parameters', parameters)
    # Extract parameters
    ubidots_token = parameters.get('token')

    # AWS Data
    bucket_name = parameters.get('bucket_name')
    upload_path = parameters.get('upload_path')
    aws_region = parameters.get('awsRegion')
    iam_account = parameters.get('iam_account')
    role_trusted = parameters.get('role_trusted')

    # Timezone Data
    time_zone = parameters.get('time_zone')

    # Backup Time Data
    backup_range = parameters.get('backup_range')

    # Zip or CSV - Future Use
    # compress = parameters.get('compress')

    # Data Entity Data
    filter_name = parameters.get('filter_name')
    data_entity_organizations = parameters.get('data_entity_organizations')
    data_entity_device_groups = parameters.get('data_entity_device_groups')
    data_entity_device_types = parameters.get('data_entity_device_types')

    # Calculate start and end based on backup_range
    now = arrow.utcnow()
    print('now', now)
    start, end = get_time_frame(now, backup_range)
    print('start', start)
    print('end', end)

    # Set up parameters object
    parameters = {'start': start * 1000,
                  'end': end * 1000,
                  'bucketName': bucket_name,
                  'awsRegion': aws_region,
                  'tz': time_zone,
                  'uploadPath': upload_path,
                  'filterName': filter_name,
                  'dataEntityOrganizations': data_entity_organizations,
                  'dataEntityDeviceGroups': data_entity_device_groups,
                  'dataEntityDeviceTypes': data_entity_device_types,
                  'iamAccount': iam_account,
                  'roleTrusted': role_trusted}

    json_parameters = json.dumps(parameters)
    print('parameters', parameters)
    print('json_parameters', json_parameters)
    # Make request to Ubidots backup endpoint
    url = 'https://industrial.api.ubidots.com/api/-/account/_/export-data/'
    # url = 'https://enpndx4nvztv.x.pipedream.net'
    headers = {'X-Auth-Token': ubidots_token, 'Content-Type': 'application/json'}

    make_request(url, headers, attempts=3, http_method='POST', data=json_parameters)
    return {'message': 'S3 Backup Process Successfully Started.'}


def make_request(url, headers, attempts, http_method='POST', data=None):
    '''
    Function to make a request to the ubidots server
    '''
    try:
        req = requests.request(method=http_method, url=url,
                               headers=headers, data=data)
        print("req", req)
        print("req", req.__dict__)
        print('[INFO] Ubidots request result: {}'.format(req.text))
        status_code = req.status_code
        print("status_code", status_code)
        time.sleep(1)
        while status_code >= 400 and attempts < 5:
            req = requests.request(
                method=http_method, url=url, headers=headers, data=data)
            print('[INFO] Ubidots request result: {}'.format(req.text))
            status_code = req.status_code
            attempts += 1
            time.sleep(1)
        return req
    except Exception as e:
        print('[ERROR] There was an error with the request, details:')
        print(e)
        return None


def get_time_frame(actual_time, time_frame='D'):
    '''Get a given time frame based on the actual time passed by the user.

    :params actual_time: The time passed by the user. Should be an Arrow instance.
    '''
    time_frames = {
        # This month
        'MS': {'start': lambda now: now.floor('month').timestamp, 'end': lambda now: now.ceil('day').timestamp},
        # Last 7 days
        '7D': {
            'start': lambda now: (now.floor('day') - relativedelta(days=7)).timestamp,
            'end': lambda now: (now.ceil('day') - relativedelta(days=1)).timestamp,
        },
        # Today
        'D': {'start': lambda now: now.floor('day').timestamp, 'end': lambda now: now.ceil('day').timestamp},
        # Last month
        '2MS': {
            'start': lambda now: get_last_month_time_frame(now)[0],
            'end': lambda now: get_last_month_time_frame(now)[1],
        },
        # Last week
        '168H': {
            'start': lambda now: (now - relativedelta(days=now.weekday() + 7)).floor('day').timestamp,
            'end': lambda now: (now - relativedelta(days=now.weekday() + 1)).ceil('day').timestamp,
        },
        # Last 24 hours
        '24H': {'start': lambda now: (now - relativedelta(hours=24)).timestamp, 'end': lambda now: now.timestamp},
        # Yesterday
        '2D': {
            'start': lambda now: (now.floor('day') - relativedelta(days=1)).timestamp,
            'end': lambda now: (now.ceil('day') - relativedelta(days=1)).timestamp,
        },
        # This week
        'W': {
            'start': lambda now: (now.floor('day') - relativedelta(days=now.weekday())).timestamp,
            'end': lambda now: now.ceil('day').timestamp,
        },
        # Last 30 days
        '30D': {
            'start': lambda now: (now.floor('day') - relativedelta(days=30)).timestamp,
            'end': lambda now: (now.ceil('day') - relativedelta(days=1)).timestamp,
        },
    }
    current_time_frame = time_frames.get(time_frame, None)
    if current_time_frame is None:
        return None, None
    start_function = current_time_frame.get('start')
    start = None
    end = None
    if start_function is not None:
        start = start_function(actual_time)
    end_function = current_time_frame.get('end')
    if end_function is not None:
        end = end_function(actual_time)
    return start, end


def get_last_month_time_frame(now):
    # first date of the last month
    first_last_month_date = now.floor('day').replace(day=1) - relativedelta(months=1)

    # last month date
    _, last_month_day = monthrange(first_last_month_date.year, first_last_month_date.month)
    last_month_date = now.floor('day').replace(day=1) - relativedelta(months=1) + relativedelta(days=last_month_day)

    # timestamps
    first_last_month_date_timestamp = first_last_month_date.timestamp
    last_month_date_timestamp = last_month_date.timestamp

    return first_last_month_date_timestamp, last_month_date_timestamp
