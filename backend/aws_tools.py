import boto.ec2
import os
import csv
import boto.manage.cmdshell

######################################################################
# Script to launch an instance and load the search engine
# To run this script have the credential csv file provided
# by aws with access keys in the same directory
# and the script will return the instance ID and public IP address

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


# Create a key pair and save the key pair
key_pair = conn.create_key_pair("puddle_key_pair")
if key_pair.save("."):
    print "Save successful"
else:
    print "Save not successful"
'''
'''
# Create a security group
security_group = conn.create_security_group("csc326-group013", "Security group for the puddle search engine")


security_group.authorize(ip_protocol="ICMP", from_port=-1, to_port=-1, cidr_ip="0.0.0.0/0")
security_group.authorize(ip_protocol="TCP", from_port=22, to_port=22, cidr_ip="0.0.0.0/0")
security_group.authorize(ip_protocol="TCP", from_port=80, to_port=80, cidr_ip="0.0.0.0/0")



# Run an instance on t1.micro with ubuntu image
puddle_instance = conn.run_instances(image_id='ami-8caa1ce4', key_name='puddle_key_pair', security_groups=['csc326-group013'], instance_type='t1.micro', user_data = """
#!/bin/bash
sudo apt-get update
sudo apt-get install python-pip -y
sudo pip install BeautifulSoup
sudo apt-get install python-dev -y
sudo pip install numpy
sudo pip install bottle
sudo pip install oauth2client
sudo pip install google-api-python-client
sudo pip install beaker
sudo pip install redis
sudo apt-get install redis-server -y
nohup redis-server &""")


print "Waiting for instance to be initialized, this may take a while"
instance = puddle_instance.instances[0]
while instance.state != 'running':
    instance.update()


public_dns_name = instance.public_dns_name
instance_status = conn.get_all_instance_status(instance_ids=[instance.id])

while instance_status[0].instance_status.status != 'ok':

    instance.update()
    instance_status = conn.get_all_instance_status(instance_ids=[instance.id])

print "Instance is ready"

print "Adding and running search engine code"

cmd = boto.manage.cmdshell.sshclient_from_instance(instance, "puddle_key_pair.pem", user_name='ubuntu')


# Add all the source code
os.system("scp -o StrictHostKeyChecking=no -i puddle_key_pair.pem urls.txt ubuntu@"+public_dns_name+":~")

os.system("scp -o StrictHostKeyChecking=no -i puddle_key_pair.pem urls.txt ubuntu@"+public_dns_name+":~")

os.system("scp -o StrictHostKeyChecking=no -i puddle_key_pair.pem searchEngine.py ubuntu@"+public_dns_name+":~")

os.system("scp -o StrictHostKeyChecking=no -i puddle_key_pair.pem ./frontend/html/errorpage.html ubuntu@"+public_dns_name+":~/frontend/html")

os.system("scp -o StrictHostKeyChecking=no -i puddle_key_pair.pem ./frontend/html/output.html ubuntu@"+public_dns_name+":~/frontend/html")

os.system("scp -o StrictHostKeyChecking=no -i puddle_key_pair.pem ./frontend/html/querypage.html ubuntu@"+public_dns_name+":~/frontend/html")

os.system("scp -o StrictHostKeyChecking=no -i puddle_key_pair.pem ./frontend/html/resultpage.html ubuntu@"+public_dns_name+":~/frontend/html")

os.system("scp -o StrictHostKeyChecking=no -i puddle_key_pair.pem ./frontend/images/logo.png ubuntu@"+public_dns_name+":~/frontend/images")

os.system("scp -o StrictHostKeyChecking=no -i puddle_key_pair.pem ./frontend/images/puddle.jpg ubuntu@"+public_dns_name+":~/frontend/images")

# Run the code
(status, std_out, std_err) = cmd.run("python crawler.py")

(status, std_out, std_err) = cmd.run("python searchEngine.py")

print "Puddle is now ready!"

print "Instance IP Address : " + str(instance.ip_address)
print "Instance ID : " + str(instance.id)







