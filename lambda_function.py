import json
import boto3
import botocore.exceptions
import time
import datetime

SOURCE_REGION = "us-west-2"
SOURCE_RESOURCE  = boto3.resource("ec2", region_name=SOURCE_REGION)
SOURCE_CLIENT = boto3.client("ec2", region_name=SOURCE_REGION)
DEST_ACCOUNT_ID = "123xxxxxxxxx"
DEST_REGIONS = ["us-west-2", "us-east-1", "eu-central-1", "ap-northeast-1", "ap-southeast-1", "ap-southeast-2", "ca-central-1"]

def copy_ami():
  # Assume Role to access EC2 in another account
  sts_client = boto3.client("sts")
  assumeRole = sts_client.assume_role(
    RoleArn="arn:aws:iam::" + DEST_ACCOUNT_ID + ":role/cross-account-role",
    RoleSessionName="AssumeRoleSession1")
  creds = assumeRole["Credentials"]
  
  images = SOURCE_RESOURCE.images.filter(Filters=[{"Name":"tag:prod_approved", "Values":["true"]}])
  for image in images:
    if "copy_timestamp" not in json.dumps(image.tags):
      image.modify_attribute(
        ImageId = image.id,
        Attribute = "launchPermission",
        OperationType = "add",
        LaunchPermission = {
          "Add" : [{ "UserId": DEST_ACCOUNT_ID }]
        }
      )
        
      devices = image.block_device_mappings
      for device in devices:
        if "Ebs" in device:
          snapshot_id = device["Ebs"]["SnapshotId"]
          snapshot = SOURCE_RESOURCE.Snapshot(snapshot_id)
          snapshot.modify_attribute(
            Attribute = "createVolumePermission",
            CreateVolumePermission = {
              "Add" : [{ "UserId": DEST_ACCOUNT_ID }]
            },
              OperationType = "add",
          )
      
        for region in DEST_REGIONS:
          ec2_client = boto3.client("ec2", aws_access_key_id=creds["AccessKeyId"],
                                    aws_secret_access_key=creds["SecretAccessKey"],
                                    aws_session_token=creds["SessionToken"], region_name=region)
          if image.id not in json.dumps(ec2_client.describe_images(Filters=[{"Name":"name", "Values":[image.name]}], Owners=[DEST_ACCOUNT_ID])):
            new_image = ec2_client.copy_image(
              Description=image.id,
              Encrypted=True,
              Name=image.name,
              SourceImageId=image.id,
              SourceRegion=SOURCE_REGION
            )
            
            ec2_client.create_tags(
              Resources=[new_image["ImageId"]],
              Tags=source_tags
            )
            time.sleep(10)
      
        SOURCE_CLIENT.create_tags(
          Resources=[image.id],
          Tags = [
            {
              "Key": "copy_timestamp",
              "Value": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
          ] 
        )
    
def lambda_handler(event, context):
  copy_ami()
