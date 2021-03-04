import json
from os import remove
from zipfile import ZipFile
import boto3
import requests
from time import sleep

kwargs = {
    'aws_credentials': {
        'aws_access_key_id': 'AKIATLNYSVJYWDISW7RF',
        'aws_secret_access_key': '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',
    },
    'awsRegion': 'us-east-1',
    'memory_retention': '720',
    'magnetic_retention': '30',
    'bucket_name': 'test-holberton',
    'upload_path': 'ubidots'
}


def setup(kwargs):
    print('Inside Setup function of control.py (AWS TimeStream Data Plugin)')
    # Get info
    aws_credentials = kwargs.get('aws_credentials')
    print('aws_credentials', aws_credentials)
    region_name = kwargs.get('awsRegion')
    print('region_name', region_name)
    memory_retention = kwargs.get('memory_retention')
    print('memory_retention', memory_retention)
    magnetic_retention = kwargs.get('magnetic_retention')
    print('magnetic_retention', magnetic_retention)
    bucket_name = kwargs.get('bucket_name')
    print('bucket_name', bucket_name)
    upload_path = kwargs.get('upload_path')
    print('upload_path', upload_path)

    # Login
    Session, user_id = login(aws_credentials, region_name)

    # Create rol for lambda with s3 and timestream policies
    role_name = create_rol(Session, user_id, bucket_name)

    # Prepare code for lambda function
    zip_file = prepare_code(memory_retention, magnetic_retention)

    # Create lambda function
    lambda_function_name = create_lambda_function(Session, user_id, role_name, zip_file)

    # Configure the s3 trigger
    trigger_configuration(Session, lambda_function_name, user_id, bucket_name, upload_path, region_name)

    return {'status': 200, 'message': 'Control.py successfully executed'}


def login(aws_credentials, region_name):
    print('Inside login function')
    if aws_credentials is not None:
        aws_access_key_id = (
                aws_credentials.get('AccessKeyId') or aws_credentials.get(
            'aws_access_key_id') or aws_credentials.get('access_key')
        )
        aws_secret_access_key = (
                aws_credentials.get('SecretAccessKey')
                or aws_credentials.get('aws_secret_access_key')
                or aws_credentials.get('secret_key')
        )
        aws_session_token = (
                aws_credentials.get('SessionToken') or aws_credentials.get(
            'aws_session_token') or aws_credentials.get('token')
        )
    else:
        aws_access_key_id = None
        aws_secret_access_key = None
        aws_session_token = None
    session = boto3.session.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        # aws_session_token=aws_session_token,
        region_name=region_name
    )
    print('[login] session', session)

    return session, session.client('sts').get_caller_identity()['Account']


def create_rol(Session, user_id, bucket_name):
    iam = Session.client('iam')
    response = iam.create_role(
        RoleName='ubidots_lambda_role',
        AssumeRolePolicyDocument=json.dumps({
            'Version': '2012-10-17',
            'Statement': [{
                'Effect': 'Allow',
                'Action': 'sts:AssumeRole',
                'Principal': {'Service': 'lambda.amazonaws.com'},
            }]
        }))
    response = iam.create_policy(
        PolicyName='ubidots_s3_timestream',
        PolicyDocument= json.dumps({
            'Version': '2012-10-17',
            'Statement': [
                {
            'Sid': 'VisualEditor0',
            'Effect': 'Allow',
            'Action': [
                's3:GetObject',
                'timestream:WriteRecords',
                'timestream:CreateDatabase',
                'timestream:UpdateDatabase',
                'timestream:UpdateTable',
                'timestream:CreateTable'
            ],
            'Resource': [
                'arn:aws:s3:::{}/*'.format(bucket_name),
                'arn:aws:timestream:*:*:database/ubidots_s3_backup/table/*',
                'arn:aws:timestream:*:*:database/ubidots_s3_backup'
            ]
        },
        {
            'Sid': 'VisualEditor1',
            'Effect': 'Allow',
            'Action': 'timestream:DescribeEndpoints',
            'Resource': '*'
        },
        {
            'Sid': 'VisualEditor2',
            'Effect': 'Allow',
            'Action': [
                'logs:CreateLogGroup',
                'logs:CreateLogStream',
                'logs:PutLogEvents'
            ],
            'Resource': '*'
        }
            ]
        }),
        Description='Policy to get object from s3 and write it into TimeStream',
    )
    response = iam.attach_role_policy(
        RoleName='ubidots_lambda_role',
        PolicyArn='arn:aws:iam::{}:policy/ubidots_s3_timestream'.format(user_id)
    )
    sleep(7) # Pendiente por preguntar

    return 'ubidots_lambda_role'


def prepare_code(memory_retention, magnetic_retention):
    with open('retention_times.py', 'a') as f:
        f.write('memory_retention = {} \n'.format(memory_retention))
        f.write('magnetic_retention = {}'.format(magnetic_retention))
    # Change for real URL
    code = requests.get('https://raw.githubusercontent.com/oimoralest/timestream_plugin/main/lambda_timestream_backup.py?token=APW3MKA7N3HT5QUL7CRB7NDAJDXD2').text
    with open('lambda_base_code.py', 'w') as f:
        f.write(code)
    with ZipFile('lambda_base_code.zip', 'a') as zip_file:
        zip_file.write('retention_times.py')
        zip_file.write('lambda_base_code.py')
    remove('retention_times.py')
    remove('lambda_base_code.py')

    return 'lambda_base_code.zip'


def create_lambda_function(Session, user_id, role_name, zip_file):
    aws_lambda = Session.client('lambda')
    try:
        with open(zip_file, 'rb') as f:
            response = aws_lambda.create_function(
                FunctionName='lambda_base_code',
                Runtime='python3.7',
                Role='arn:aws:iam::{}:role/{}'.format(user_id, role_name), # Change for real rol name (trusted_rol)
                Handler='lambda_base_code.lambda_handler',
                Code={
                    'ZipFile': f.read(),
                    #'S3Bucket': '{}'.format(bucket_name),
                    #'S3Key': 'lambda_test.zip'
                }
            )
    except Exception as err:
        print(err.response)
    remove('lambda_base_code.zip')

    return 'lambda_base_code'


def trigger_configuration(Session, lambda_function_name, user_id, bucket_name, upload_path, region_name):
    aws_lambda = Session.client('lambda')
    s3 = Session.client('s3')
    try:
        response = aws_lambda.add_permission(
            FunctionName='arn:aws:lambda:{}:{}:function:{}'.format(region_name, user_id, lambda_function_name),
            StatementId='Invoke',
            Action='lambda:InvokeFunction',
            Principal='s3.amazonaws.com',
            SourceArn='arn:aws:s3:::{}'.format(bucket_name) # Change for real bucket name
        )
    except Exception as err:
        print(err)
    response = aws_lambda.get_policy(
        FunctionName='arn:aws:lambda:{}:{}:function:{}'.format(region_name, user_id, lambda_function_name)
    )
    response = s3.put_bucket_notification_configuration(
        Bucket='{}'.format(bucket_name), # Change for real bucket name
        NotificationConfiguration={
            'LambdaFunctionConfigurations': [
                {
                    'LambdaFunctionArn': 'arn:aws:lambda:{}:{}:function:{}'.format(region_name, user_id, lambda_function_name),
                    'Events': ['s3:ObjectCreated:*'],
                    'Filter': {
                        'Key': {
                            'FilterRules': [
                                {
                                    'Name': 'prefix',
                                    'Value': '{}'.format(upload_path) # Change for real path name
                                }
                            ]
                        }
                    }
                }
            ]
        }
    )

    return response


setup(kwargs)
