# Deployment and Hosting

The site is hosted as a static site on AWS/S3.

To (re-)create the S3 bucket setup in the eu-central-1 region, run the following:

Prerequisites:

- AWS CLI
- AWS credentials with permissions to create and manage S3 buckets

Create the bucket:

```bash
aws s3api create-bucket --bucket <bucket-name> --region eu-central-1 --create-bucket-configuration LocationConstraint=eu-central-1
```

Configure public access settings:

```bash
aws s3api put-public-access-block --bucket <bucket-name> --public-access-block-configuration "BlockPublicPolicy=false"
```

Verify the configuration:

```bash
aws s3api get-bucket-ownership-controls --bucket <bucket-name>
```

Apply public read policy:

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

Deploy website to S3:

```bash
aws s3 cp tmp/ s3://<bucket-name>/ --recursive
```

Configure website index document:

```bash
aws s3 website s3://<bucket-name> --index-document index.html
```

Verify deployment:

```bash
curl <bucket-name>.s3-website.eu-central-1.amazonaws.com
```

For SSL and custom domain setup, see the AWS S3 bucket properties page:
https://eu-central-1.console.aws.amazon.com/s3/buckets/<bucket-name>?region=eu-central-1&bucketType=general&tab=properties

## Automated Deployment

GitHub Actions handles automated building and deployment. See `.github/workflows/main.yml` for implementation details.

Required GitHub secrets:

- AWS_S3_BUCKET
- AWS_REGION
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY

## Manual Deployment

Use GitHub Actions for deployment to maintain consistency. Manual deployment risks creating discrepancies.

For emergency deployments only:

```bash
make build
aws s3 cp tmp/ s3://<bucket-name>/ --recursive
```
