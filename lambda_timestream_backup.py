import boto3
from zipfile import ZipFile
import json
import csv
from retention_times import memory_retention, magnetic_retention


def read_s3(Session, event):
    """read_s3 method.

    This method gets an object from an AWS S3 bucket (Backup previously made by
    the plugin AWS Timestream) and prepares the data stored in to be written in
    AWS Timestream

    Args:
        Session: boto3 Session that allows to create service clients and
        resources
        event: Information about the object set in the trigger

    Returns:
        the records to be stored and the name of the table to be create in
        timestream or None on error
    """
    print('Reading s3', event)
    # Creates a s3 client
    s3 = Session.client('s3')
    # Get info from a new bucket object
    s3_bucket_object = event.get('Records')[0].get('s3').get('object')
    s3_bucket_name = event.get('Records')[0].get('s3').get('bucket').get('name')
    # Get the name of the zip File
    for item in s3_bucket_object.get('key').split('/'):
        if '.zip' in item:
            zip_file = item
    # Download the file from the client's S3 bucket
    print('Bucket: ', s3_bucket_name)
    print('Object: ', s3_bucket_object.get('key'))
    s3.download_file(
        s3_bucket_name,
        s3_bucket_object.get('key'),
        '/tmp/{}'.format(zip_file)
    )
    # Treatment of data to format it for TimeStream
    # open file zip
    with ZipFile('/tmp/{}'.format(zip_file), 'r') as zip:
        records = []
        # Go over each csv file
        for file_name in zip.namelist():
            if '.csv' not in file_name:
                continue
            with zip.open(file_name, 'r', pwd=None) as csv_file:
                print('csv_file: ', csv_file)
                device_name = file_name.split('/')[0]
                attribute_name = file_name.split('/')[1]
                variable_name = file_name.split('/')[2]
                # Each line needs to be decode into utf-8
                lines = [line.decode('utf-8') for line in csv_file.readlines()]
                reader = csv.reader(lines)
                parsed_csv = list(reader)
                for row in parsed_csv[1:]:
                    # Clean the contest variable inside csv file
                    context = json.loads(row[3][2:-1])
                    dimensions = [{
                                'Name': 'device',
                                'Value': attribute_name
                            }]
                    # If context is not empty, it is added to the dimension
                    if len(context) != 0:
                        for key, value in context.items():
                            dimensions.append({
                                'Name': key,
                                'Value': str(value)
                            })
                    # Each line is stored as new timestream record
                    records.append({
                        'Dimensions': dimensions,
                        'MeasureName': variable_name,
                        'MeasureValue': row[2],
                        'Time': row[0],
                    })
    # If the zip file is empty or non csv files were found
    if records is []:
        return None, None
    return records, device_name


def write_timestream(Session, records, t_name):
    """write_timestream method

    This method write records on AWS timestream

    Args:
        Session: boto3 Session that allows to create service clients and
        resources
        records: data to be stored in AWS timestream
        t_name: table name to be created in AWS timestream inside
        ubidots_s3_backup

    Returns:
        Nothing
    """
    timestream = Session.client('timestream-write')
    # Crea la base de datos si no existe
    try:
        timestream.create_database(
            DatabaseName='ubidots_s3_backup'
        )
    # Condicional para evaluar si existe la base de datos: botocore.exceptions.ConflictException
    except timestream.exceptions.ConflictException:
        print('Database already exists')
        pass
    # Crea la table si no existe
    try:
        timestream.create_table(
            DatabaseName='ubidots_s3_backup',
            TableName=t_name,
            RetentionProperties={
                'MemoryStoreRetentionPeriodInHours': memory_retention,
                'MagneticStoreRetentionPeriodInDays': magnetic_retention
            }
        )
    # Condicional para evaluar si existe la tabla: botocore.exceptions.ConflictException
    except timestream.exceptions.ConflictException:
        print('Table already exists. Updating table properties')
        timestream.update_table(
            DatabaseName='ubidots_s3_backup',
            TableName=t_name,
            RetentionProperties={
                'MemoryStoreRetentionPeriodInHours': memory_retention,
                'MagneticStoreRetentionPeriodInDays': magnetic_retention
            }
        )
    # Escribe los registros
    try:
        timestream.write_records(
                DatabaseName='ubidots_s3_backup',
                TableName=t_name,
                Records=records
        )
    # Ocurre cuando los datos no estan dentro del rango del tiempo de retencion
    except timestream.exceptions.RejectedRecordsException as err:
        print('Warning: Some records were rejected. See RejectedRecords for \
        more information')
        print('RejectedRecords: ', err.response['RejectedRecords'])

def lambda_handler(event, context):
    """lambda_handler method.

    This method is the handler for the AWS Lambda function

    Args:
        event: Information about the object set in the trigger
        context: LambdaContext Object

    Returns:
        status code 200 on succesful execution, otherwise 400 with its
        corresponding message
    """
    Session = boto3.Session()
    records, device_name = read_s3(Session, event)
    if records is None and device_name is None:
        return {
            'statusCode': 400,
            'body': json.dumps('No records found!')
        }
    else:
        write_timestream(Session, records, device_name)
    return {
        'statusCode': 200,
        'body': json.dumps('Records written successfully!')
    }
