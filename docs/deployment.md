# Deployment/Hosting

The site is hosted as a static site on AWS/S3.

To (re-)create the S3 bucket setup in the eu-central-1 region, run the following:

Prerequisites:

- aws-cli
- aws credentials that allow you to create and manage S3 buckets

Create the bucket:

```bash
aws s3api create-bucket --bucket <bucket-name> --region eu-central-1 --create-bucket-configuration LocationConstraint=eu-central-1
```

Allow policies to set public access:

```bash
aws s3api put-public-access-block --bucket <bucket-name> --public-access-block-configuration "BlockPublicPolicy=false"
```

Check that the settings are correct:

```bash
aws s3api get-bucket-ownership-controls --bucket <bucket-name>
```

Allow public read through policy.

```bash
aws s3api put-bucket-policy --bucket <bucket-name> --policy '{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": [
                "s3:GetObject"
            ],
            "Resource": [
                "arn:aws:s3:::'<bucket-name>'/*"
 
            ]
        }
    ]
}'
```

Copy website to s3:

```bash
aws s3 cp tmp s3://<bucket-name>/ --recursive
```

Set index:

```bash
aws s3 website s3://<bucket-name> --index-document index.html
```

Confirm the results:

```bash
curl <bucket-name>.s3-website.eu-central-1.amazonaws.com
```

AWS provides in-depth guides on how to setup SSL and your domain, check it out on the buckets' page:
https://eu-central-1.console.aws.amazon.com/s3/buckets/<bucket-name>?region=eu-central-1&bucketType=general&tab=properties

### Automation

A github action workflow is provided and will take care of building and deployment. Check out `./.github/workflows/main.yml` for details.

Don't forget to set the following secrets in the github project:

- AWS_S3_BUCKET
- AWS_REGION
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY

### Manual Deployment

You should probably not do that and rely on the github action for this. Otherwise you might have a local version deployed that is not
reflected upstream.
But there will be the possibility for an emergency situation where you will need to quickly upload a hotpatch and can't wait for the github
action. We have all been there:

```bash
make build
aws s3 cp tmp s3://<bucket-name>/ --recursive
```
