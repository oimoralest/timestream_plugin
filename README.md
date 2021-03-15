# DATAPLUGIN TIMESTREAM
<div align="center">
<img src="https://github.com/oimoralest/timestream_plugin/blob/main/images/product_cover.png" alt="Dataplugin"/>
</div>


## Description

> Due to the needs in the analysis of this information, we develop a dataplugin that allows to articulate the information collected by the company through the devices, performing a periodic backup in an S3 bucket that is migrated to a database from AWS Timestream and thus, improve the compatibility of the data for its integration with the rest of the services offered by Amazon Web Services and other services such as Grafana.

## Technologies

> - Python 3.7
> - Boto3 (SDK for python)
> - JSON
> - XML
> - AWS Cloudwatch
> - AWS S3 (Storage)
> - AWS Timestream (Time series data base)

## Table of contents

| FILES | DESCRIPTION |
| ----- | ----------- |
| src/control.py | <p> Contains the functions:<blockquote>**setup**: Set all the variables to execute the dataplugin. <br><br>**login**: Use the kwargs to log into the user's AWS account. <br><br>**create_role**: Creates IAM role( permissions for AWS services) </p>|
| src/function.py |<p> Contains the fucntions:<blockquote> **main**: Principal function that takes  AWS data, timezone data,  backup time data and set up parameters object.<br><br>**make_request**: Make a request to the ubidots server.<br><br>**get_time_frame**: Get a given time frame based on the actual time passed by the user.<br><br>**get_last_month_time_frame**: First date of the last month.</p>|
| src/lambda_timestream_backup.py |<p> Contains the functions: <blockquote>**read_s3**: Gets an object from an AWS S3 bucket and prepares the data stored (AWS Timestream). <br><br>**write_timestream**: Write records on AWS timestream. <br><br>**lambda_handler**: Handler for the AWS Lambda function.  </p>
| src/view.xml | <blockquote>Contains the form with the fields required for the plugin working.|
| manifest.json | <blockquote>Describes essential information about the plugin |
|LICENSE | <blockquote>**MIT License** ( Copyright (c) 2021 Ubidots ) |


## Infraestructure

> Below, we present the general infrastructure of this project, which was carried out as a final project for Holberton School to the Ubidots company.

# ![Infrastructure](https://github.com/oimoralest/timestream_plugin/blob/main/images/infraestructure.png)

## Usage

Read more : (https://github.com/oimoralest/timestream_ubidots/documentation.pdf)

## Demo

> Here is a working live demo: (https://drive.google.com/file/d/11ru1DBxqjo8AOQpEgFnb5KyIoKEA7Oob/view)

## Team
> Laura Álvarez - Manager Engineer and Full Stack Developer (apla02@gmail.com)<br>
Fabian Carmona - Product Design Engineer and Full Stack Developer (carmona.vargas.fabian@gmail.com)<br>
Luis Carvajal - Mechatronic Engineer Stud. and Full Stack Developer (luiscarvajal05@gmail.com)<br>
Luis Calderón Mechanical Engineer and Full Stack Developer (luismiguel.calderone@gmail.com)<br>
Óscar Morales - Chemical Engineer and Full Stack Developer (oimoralest@gmail.com)

## License
**MIT License** - Copyright (c) 2021 Ubidots 
