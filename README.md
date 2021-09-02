ami-copy-cross-accounts
===

# About
This Lambda will autocopy an AMI from one account to another accross multiple regions.

## Requirements
To invoke the lambda function, you will need to tag the AMI the following:

```
copy_approved = true
```
