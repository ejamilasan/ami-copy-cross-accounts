import json
import boto3
import botocore.exceptions
import time

SOURCE_REGION = "us-west-2"
SOURCE_CLIENT  = boto3.resource("ec2", region_name=SOURCE_REGION)
DEST_ACCOUNT_ID = "123xxxxxxxxx"
DEST_REGIONS = ["us-west-2", "us-east-1"]

def copy_ami():
  # Assume Role to access EC2 in DEST_ACCOUNT
  sts_client = boto3.client("sts")
  assumeRole = sts_client.assume_role(
    RoleArn="arn:aws:iam::" + DEST_ACCOUNT_ID + ":role/cross-account-role",
    RoleSessionName="AssumeRoleSession1")
  creds = assumeRole["Credentials"]

  images = SOURCE_CLIENT.images.filter(Filters=[{"Name":"tag:copy_approved", "Values":["true"]}])
  for image in images:
    image = SOURCE_CLIENT.Image(image.id)
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
        snapshot = SOURCE_CLIENT.Snapshot(snapshot_id)
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
          source_tags = image.tags
          source_tags.append(
            {
              "Key": "name",
              "Value": "ami-copy"
            }
          )
          ec2_client.create_tags(
            Resources=[new_image["ImageId"]],
            Tags=source_tags
          )
          time.sleep(5)
    
def lambda_handler(event, context):
  copy_ami()
