import boto.ec2
import sys
import csv

##################################################
# Script to terminate an instance
# To run this script have the credential csv file provided
# by aws with access keys in the same directory
# and pass the instance ID as command line argument


with open("credentials.csv") as key_file:
    csv_reader = csv.reader(key_file)
    first_line = csv_reader.next()
    list_key = csv_reader.next()

    # Access key and secret access key
    access_key_id = list_key[1]
    secret_access_key = list_key[2]


# Connect to US east with secret access keys
conn = boto.ec2.connect_to_region('us-east-1',
                                  aws_access_key_id=access_key_id,
                                  aws_secret_access_key=secret_access_key)
if len(sys.argv) == 2:
    instance_id = str(sys.argv[1])
else:
    print "Please add the instance ID as a command line argument"
    sys.exit(0)

# e_ip = conn.release_address()

terminated_instance = conn.terminate_instances([instance_id])



if terminated_instance:
    print str(terminated_instance[0].id) + " has been terminated"
else:
    print instance_id + " has not been termianted"
