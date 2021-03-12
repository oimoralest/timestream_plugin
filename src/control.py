"""This module setup the data plugin
"""
import json
from datetime import date
from os import remove
from time import sleep
from zipfile import ZipFile
import botocore
import boto3
import requests


GITHUB_URL = "https://raw.githubusercontent.com/oimoralest/timestream_plugin/main/src/lambda_timestream_backup.py?token=APW3MKEELNFUJM2WUTCKDYLAKJ5XM"


def setup(kwargs):
    """This method will set all the required variables to execute the plugin.

    Args:
        kwargs: Ubidots parameters from the backend

    Returns:
        Status code and the corresponding message
    """
    print("Inside Setup function of control.py (AWS TimeStream Data Plugin)")
    # Get info
    aws_credentials = kwargs.get("aws_credentials")
    print("aws_credentials", aws_credentials)
    region_name = kwargs.get("awsRegion")
    print("region_name", region_name)
    memory_retention = kwargs.get("memory_retention")
    print("memory_retention", memory_retention)
    magnetic_retention = kwargs.get("magnetic_retention")
    print("magnetic_retention", magnetic_retention)
    bucket_name = kwargs.get("bucket_name")
    print("bucket_name", bucket_name)
    upload_path = kwargs.get("upload_path")
    print("upload_path", upload_path)
    table_name = kwargs.get("table_name")
    print("table_name", table_name)
    # Login
    session, user_id = login(aws_credentials, region_name)
    if session is None:
        return {"status": 400, "message": "Unable to locate credentials"}
    # Creates role for lambda with s3 and timestream policies
    role_name = create_role(session, user_id, bucket_name)
    if role_name is None:
        return {"status": 400, "message": "Role could not be created"}
    # Prepares code for lambda function
    zip_file = prepare_code(memory_retention, magnetic_retention, table_name)
    if zip_file is None:
        return {"status": 400, "message": "Code is not available to be used"}
    # Creates lambda function
    lambda_function_name = create_lambda_function(
        session, user_id, role_name, zip_file)
    if lambda_function_name is None:
        return {"status": 400, "message": "Lambda function could not be \
                created or already exists"}
    # Configures the s3 trigger
    response = configure_s3_trigger(
        session, lambda_function_name, user_id, bucket_name, upload_path,
        region_name)
    if response == "Error":
        return {"status": 400, "message": "Trigger could not be configured"}
    return {"status": 200, "message": "Control.py successfully executed"}


def login(aws_credentials, region_name):
    """This method will use the kwargs to log into the user's AWS account

    Args:
        aws_credentials: verify who you are and whether you have permission
        to access the resources that you are requesting
        region_name: AWS region name

    Returns:
        * boto3 session: allows to create service clients and use resources
        * user_id: AWS user's id
    """
    print("Inside login function")
    if aws_credentials is not None:
        aws_access_key_id = (
            aws_credentials.get("AccessKeyId")
            or aws_credentials.get("aws_access_key_id")
            or aws_credentials.get("access_key")
        )
        aws_secret_access_key = (
            aws_credentials.get("SecretAccessKey")
            or aws_credentials.get("aws_secret_access_key")
            or aws_credentials.get("secret_key")
        )
        aws_session_token = (
            aws_credentials.get("SessionToken")
            or aws_credentials.get("aws_session_token")
            or aws_credentials.get("token")
        )
    else:
        aws_access_key_id = None
        aws_secret_access_key = None
        aws_session_token = None
    session = boto3.session.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_session_token=aws_session_token,
        region_name=region_name,
    )
    try:
        sts = session.client("sts")
        user_id = sts.get_caller_identity()["Account"]
    except botocore.exceptions.NoCredentialsError:
        return None, None
    except botocore.exceptions.ClientError:
        return None, None
    print("[login] session", session)
    return session, user_id


def create_role(session, user_id, bucket_name):
    """Creates an IAM role that defines a set of permissions for making AWS
    service requests to S3 and Timestream

    Args:
        session: allows to create service clients and use resources
        user_id: AWS user's id
        bucket_name: Name of the bucket that hold the user's data

    Returns:
        role_name: ubidots_lambda_role if an error does not occur, otherwise,
        returns None
    """
    print("Inside Creating role")
    role_name = "ubidots_s3_timestream_backup_role"
    iam = session.client("iam")
    # Creates the role
    try:
        attempts, status = 0, 400
        sleep(1)
        while status != 200 and attempts < 5:
            response = iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": "sts:AssumeRole",
                                "Principal": {
                                    "Service": "lambda.amazonaws.com"
                                    },
                            }
                        ],
                    }
                ),
            )
            status = response.get("ResponseMetadata").get("HTTPStatusCode")
            attempts += 1
    except iam.exceptions.EntityAlreadyExistsException:
        print("Role already exists. Returning: {}".format(role_name))
        return role_name
    except Exception:
        return None
    # Creates policy document taking into account the Bucket's name defined
    # by the user
    try:
        attempts, status = 0, 400
        sleep(1)
        policy_document={
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Sid": "VisualEditor0",
                                "Effect": "Allow",
                                "Action": [
                                    "s3:GetObject",
                                    "timestream:WriteRecords",
                                    "timestream:CreateDatabase",
                                    "timestream:UpdateDatabase",
                                    "timestream:UpdateTable",
                                    "timestream:CreateTable",
                                ],
                                "Resource": [
                                    "arn:aws:s3:::{}/*".format(bucket_name),
                                    """arn:aws:timestream:*:*:database/"""
                                    """ubidots_s3_backup/table/*""",
                                    """arn:aws:timestream:*:*:database/"""
                                    """ubidots_s3_backup""",
                                ],
                            },
                            {
                                "Sid": "VisualEditor1",
                                "Effect": "Allow",
                                "Action": "timestream:DescribeEndpoints",
                                "Resource": "*",
                            },
                            {
                                "Sid": "VisualEditor2",
                                "Effect": "Allow",
                                "Action": [
                                    "logs:CreateLogGroup",
                                    "logs:CreateLogStream",
                                    "logs:PutLogEvents",
                                ],
                                "Resource": "*",
                            },
                        ],
                    }
        while status != 200 and attempts < 5:
            response = iam.create_policy(
                PolicyName="ubidots_s3_timestream",
                PolicyDocument=json.dumps(policy_document),
                Description="""Policy to get an object from s3 and write it"""
                """ into TimeStream""",
            )
            status = response.get("ResponseMetadata").get("HTTPStatusCode")
            attempts += 1
    except Exception:
        print('HERE')
        return None
    # Attaches the policy document to the role created
    try:
        attempts, status = 0, 400
        sleep(1)
        while status != 200 and attempts < 5:
            response = iam.attach_role_policy(
                RoleName=role_name,
                PolicyArn="arn:aws:iam::{}:policy/ubidots_s3_timestream"
                          .format(user_id),
            )
            status = response.get("ResponseMetadata").get("HTTPStatusCode")
            attempts += 1
    except Exception as err:
        print(err)
        return None
    # Awaits for AWS services to update
    sleep(7)
    print("Role created successfully")
    return role_name


def prepare_code(memory_retention, magnetic_retention, table_name):
    """Method that prepares the lambda function, to be deployed in AWS
    adding the memory retention and magnetic retention parameters

    Args:
        memory_retention: duration for which data to be stored in the
        memory store
        magnetic_retention: duration for which data to be stored in
        the magnetic store

    Returns:
        zip_file: lambda_base_code.zip if the file was created successfully,
        otherwise, will return None
    """
    print("Inside preparing code")
    with open("retention_times.py", "w") as file:
        file.write("memory_retention = {} \n".format(memory_retention))
        file.write("magnetic_retention = {} \n".format(magnetic_retention))
        file.write("table_name = '{}'".format(table_name))
    # Change for real URL
    response = requests.get(GITHUB_URL,)
    if response.status_code != 200:
        return None
    code = response.text
    with open("lambda_base_code.py", "w") as file:
        file.write(code)
    with ZipFile("lambda_base_code.zip", "w") as zip_file:
        zip_file.write("retention_times.py")
        zip_file.write("lambda_base_code.py")
    remove("retention_times.py")
    remove("lambda_base_code.py")
    print("Code prepared successfully")
    return "lambda_base_code.zip"


def create_lambda_function(session, user_id, role_name, zip_file):
    """Method that downloads a base lambda function from a github repository,
    to be deployed in AWS

    Args:
        session: allows to create service clients and use resources
        user_id: AWS user's id
        role_name: ubidots_lambda_role
        zip_file: lambda_base_code.zip

    Returns:
        lambda_ubidots_timestream_{"Date of creation"} if the function was
        created successfully, otherwise, will return None
    """
    print("Inside creating lambda function")
    aws_lambda = session.client("lambda")
    lambda_function_name = "lambda_ubidots_timestream_{}".format(
        date.today().strftime("%m_%d_%Y_%H_%M_%S_%f")
    )
    try:
        with open(zip_file, "rb") as file:
            aws_lambda.create_function(
                FunctionName=lambda_function_name,
                Runtime="python3.7",
                Role="arn:aws:iam::{}:role/{}".format(user_id, role_name),
                Handler="lambda_base_code.lambda_handler",
                Code={
                    "ZipFile": file.read(),
                },
            )
    except Exception:
        remove("lambda_base_code.zip")
        return None
    remove("lambda_base_code.zip")
    print("Lambda function created successfully")
    return lambda_function_name


def configure_s3_trigger(
    session, lambda_function_name, user_id, bucket_name, upload_path,
    region_name
):
    """Method that creates the trigger event when an object is created in the
    designated bucket of S3 in the specified upload_path
    Args:
        session: allows to create service clients and use resources
        lambda_ubidots_timestream_{"Date of creation"}: function with the
        parameters to store data in Timestream
        user_id: Using sts "Security Token Service" obtains user's Id number
        bucket_name: Name of the container that hold the user's data
        upload_path: Path inside the S3 bucket where all data will be stored
        region_name: AWS region name
    Returns:
        None if the event notification was created successfully, otherwise,
        will return Error
    """
    print("Inside trigger configuration")
    aws_lambda = session.client("lambda")
    s3 = session.client("s3")
    try:
        aws_lambda.add_permission(
            FunctionName="arn:aws:lambda:{}:{}:function:{}".format(
                region_name, user_id, lambda_function_name
            ),
            StatementId="Invoke",
            Action="lambda:InvokeFunction",
            Principal="s3.amazonaws.com",
            SourceArn="arn:aws:s3:::{}".format(bucket_name),
        )
    except Exception:
        return None
    try:
        s3.put_bucket_notification_configuration(
            Bucket="{}".format(bucket_name),
            NotificationConfiguration={
                "LambdaFunctionConfigurations": [
                    {
                        "LambdaFunctionArn": """arn:aws:lambda:{}:{}:"""
                        """function:{}""".format(
                            region_name, user_id, lambda_function_name
                        ),
                        "Events": ["s3:ObjectCreated:*"],
                        "Filter": {
                            "Key": {
                                "FilterRules": [
                                    {
                                        "Name": "prefix",
                                        "Value": "{}".format(upload_path),
                                    }
                                ]
                            }
                        },
                    }
                ]
            },
        )
    except Exception:
        return "Error"
    return None
