import boto3


Session = boto3.session.Session(
        aws_access_key_id='AKIATLNYSVJYWDISW7RF',
        aws_secret_access_key='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',
        #aws_session_token="",
        region_name='us-east-1'
        #profile_name=""
)
user_id = Session.client('sts').get_caller_identity()['Account']

def setup(kwargs):
    return {"status": 200, "message": "Control.py successfully executed"}


def create_lambda_function(Session):
    aws_lambda = Session.client('lambda')
    with open('lambda_test.zip', 'rb') as f:
        response = aws_lambda.create_function(
            FunctionName='lambda_test',
            Runtime='python3.7',
            Role='arn:aws:iam::{}:role/lambda_role'.format(user_id), # Change for real rol name (trusted_rol)
            Handler='lambda_test.lambda_handler',
            Code={
                'ZipFile': f.read(),
                #'S3Bucket': 'test-holberton',
                #'S3Key': 'lambda_test.zip'
            }
        )


def trigger_configuration(Session):
    aws_lambda = Session.client('lambda')
    s3 = Session.client('s3')
    try:
        response = aws_lambda.add_permission(
            FunctionName='arn:aws:lambda:us-east-1:{}:function:lambda_test'.format(user_id),
            StatementId='Invoke',
            Action='lambda:InvokeFunction',
            Principal='s3.amazonaws.com',
            SourceArn='arn:aws:s3:::test-holberton' # Change for real bucket name
        )
    except Exception as err:
        print(err.response)
    response = aws_lambda.get_policy(
        FunctionName='arn:aws:lambda:us-east-1:{}:function:lambda_test'.format(user_id)
    )
    response = s3.put_bucket_notification_configuration(
        Bucket='test-holberton', # Change for real bucket name
        NotificationConfiguration={
            'LambdaFunctionConfigurations': [
                {
                    'LambdaFunctionArn': 'arn:aws:lambda:us-east-1:{}:function:lambda_test'.format(user_id),
                    'Events': ['s3:ObjectCreated:*'],
                    'Filter': {
                        'Key': {
                            'FilterRules': [
                                {
                                    'Name': 'prefix',
                                    'Value': 'ubidots' # Change for real path name
                                }
                            ]
                        }
                    }
                }
            ]
        }
    )


memory_retention = parameter.get('memory_retention') # from xml
magnetic_retention = parameter.get('magnetic_retention')

with open('data.py', 'a') as data:
    data.write('memory_retention = {}'.format(memory_retention))
    data.write('magnetic_retention = {}'.format(memory_retention))