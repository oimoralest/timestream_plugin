import boto3
from zipfile import ZipFile
import json
import csv
from data import memory_retention, magnetic_retention


def read_s3(Session, event):
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
    s3.download_file(
        s3_bucket_name, # Change for real bucket name
        s3_bucket_object.get('key'), # Change ubidots for real path name
        '/tmp/{}'.format(zip_file)
    )
    # Treatment of data to format it for TimeStream
    # open file zip
    with ZipFile('/tmp/{}'.format(zip_file), 'r') as zip:
        records = []
        # Go over each file cada archivo csv del archivo zip
        for file_name in zip.namelist():
            with zip.open(file_name, 'r', pwd=None) as csv_file:
                print('csv_file: ', csv_file)
                # Comprueba que el archivo csv no esta vacio ?
                #if csv_file._orig_compress_size == 0:
                    #continue
                device_name = file_name.split('/')[0]
                attribute_name = file_name.split('/')[1]
                variable_name = file_name.split('/')[2]
                # Cada linea es decodificada de bytes a string
                lines = [line.decode('utf-8') for line in csv_file.readlines()]
                # Cada linea es transformada en una lista
                reader = csv.reader(lines)
                parsed_csv = list(reader)
                for row in parsed_csv[1:]:
                    # Limpiar la variable context
                    context = json.loads(row[3][2:-1])
                    dimensions = [{
                                'Name': attribute_name,
                                'Value': attribute_name
                            }]
                    # Si existe contexto es anexada a las dimensiones
                    if len(context) != 0:
                        for key, value in context.items():
                            dimensions.append({
                                'Name': key,
                                'Value': str(value)
                            })
                    # Agrega la linea como un nuevo registro para TimeStream
                    records.append({
                        'Dimensions': dimensions,
                        'MeasureName': variable_name,
                        'MeasureValue': row[2],
                        'Time': row[0],
                    })
    return records, device_name


def write_timestream(Session, records, t_name):
    timestream = Session.client('timestream-write')
    # Crea la base de datos si no existe
    try:
        timestream.create_database(
            DatabaseName='ubidots_s3_backup'
        )
    # Condicional para evaluar si existe la base de datos: botocore.exceptions.ConflictException
    except timestream.exceptions.ConflictException:
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
        pass
    # Escribe los registros
    try:
        response = timestream.write_records(
                DatabaseName='ubidots_s3_backup',
                TableName=t_name,
                Records=records
        )
    # Ocurre cuando los datos no estan dentro del rango del tiempo de retencion
    except timestream.exceptions.RejectedRecordsException as err:
        print("Error:", err)
        print('**********')
        print(err.response)
        print('**********')
        print(err.response["RejectedRecords"])
        response = err.response
    return response

def lambda_handler(event, context):
    Session = boto3.Session()
    records, device_name = read_s3(Session, event)
    response = write_timestream(Session, records, device_name)
    return {
        'statusCode': 200,
        'body': json.dumps('Success!')
    }
