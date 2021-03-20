import boto3
from zipfile import ZipFile
import json
import csv
from retention_times import memory_retention, magnetic_retention, table_name
from math import ceil


def read_s3(Session, event):
    """This method gets an object from an AWS S3 bucket (Backup previously made by
    the plugin AWS S3) and prepares the data stored in to be written in
    AWS Timestream

    Args:
        Session: boto3 Session that allows to create service clients and
        resources
        event: Information about the object set in the trigger

    Returns:
        the records to be stored and the name of the table to be create in
        timestream or None on error
    """
    print('Reading s3')
    # Creates a s3 client
    s3 = Session.client('s3')
    # Get info from a new bucket object
    s3_bucket_object = event.get('Records')[0].get('s3').get('object')
    s3_bucket_name = event.get(
        'Records')[0].get('s3').get('bucket').get('name')
    # Get the name of the zip File
    print('Bucket: ', s3_bucket_name)
    print('Object: ', s3_bucket_object.get('key'))
    for item in s3_bucket_object.get('key').split('/'):
        if '.zip' in item:
            zip_file = item
    # Download the file from the client's S3 bucket
    s3.download_file(
        s3_bucket_name,
        s3_bucket_object.get('key'),
        '/tmp/{}'.format(zip_file)
    )
    # Data formatting for TimeStream
    # open file zip
    with ZipFile('/tmp/{}'.format(zip_file), 'r') as zip:
        records = []
        # Go over each csv file
        for file_name in zip.namelist():
            if '.csv' not in file_name:
                continue
            with zip.open(file_name, 'r', pwd=None) as csv_file:
                print('csv_file: ', csv_file)
                device_name = file_name.split('/')[1]
                variable_name = file_name.split('/')[2]
                # Each line needs to be decode into utf-8
                lines = [line.decode('utf-8') for line in csv_file.readlines()]
                reader = csv.reader(lines)
                parsed_csv = list(reader)
                for row in parsed_csv[1:]:
                    # Clean the context variable inside csv file
                    context = json.loads(row[3][2:-1])
                    dimensions = [{
                                'Name': 'device',
                                'Value': device_name
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
                        'MeasureValue': str(row[2]),
                        'Time': row[0],
                    })
    # If the zip file is empty or no csv files were found
    if records is []:
        return None, None
    return records


def write_timestream(Session, records, t_name):
    """This method write records on AWS timestream

    Args:
        Session: boto3 Session that allows to create service clients and
        resources
        records: data to be stored in AWS timestream
        t_name: table name to be created in AWS timestream inside
        ubidots_s3_backup

    Returns:
        Nothing
    """
    print('Writing to timestream')
    print('Number of records:', len(records))
    timestream = Session.client('timestream-write')
    # Creates the database
    try:
        print('Creating Database')
        timestream.create_database(
            DatabaseName='ubidots_s3_backup'
        )
    # Checks if the database already exists
    except timestream.exceptions.ConflictException:
        print('Database already exists')
        pass
    # Creates the table
    try:
        print('Creating table')
        timestream.create_table(
            DatabaseName='ubidots_s3_backup',
            TableName=t_name,
            RetentionProperties={
                'MemoryStoreRetentionPeriodInHours': memory_retention,
                'MagneticStoreRetentionPeriodInDays': magnetic_retention
            }
        )
    # Checks if the table already exists
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
    # Write the records
    try:
        calls = ceil(len(records) / 100)
        print('Calls:', calls)
        for i in range(calls):
            timestream.write_records(
                    DatabaseName='ubidots_s3_backup',
                    TableName=t_name,
                    Records=records[100 * i:100 * (i + 1)]
            )
    # If an error occurs the error is printed as warning
    except IndexError:
        timestream.write_records(
                    DatabaseName='ubidots_s3_backup',
                    TableName=t_name,
                    Records=records[100 * i:]
            )
    except timestream.exceptions.RejectedRecordsException as err:
        print('Warning: Some records were rejected. See RejectedRecords for \
        more information')
        print('RejectedRecords: ', err.response['RejectedRecords'])


def lambda_handler(event, context):
    """This method is the handler for the AWS Lambda function

    Args:
        event: Information about the object set in the trigger
        context: LambdaContext Object
    Returns:
        Status code and the corresponding message
    """
    Session = boto3.Session()
    records= read_s3(Session, event)
    if records is None:
        return {
            'statusCode': 400,
            'body': json.dumps('No records found!')
        }
    else:
        write_timestream(Session, records, table_name)
    return {
        'statusCode': 200,
        'body': json.dumps('Records written successfully!')
    }
