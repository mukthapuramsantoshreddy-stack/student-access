# Student Management System — AWS learning project

A small Flask demo for learning EC2, S3, IAM, VPC, CloudWatch, and SNS.

## Features
- Add and list student records (demo records are stored in a local SQLite database on the server).
- Optional upload of JPG/JPEG/PNG/GIF/WEBP/PDF files to a private S3 bucket.
- Uses the EC2 instance profile IAM role through Boto3; no hard-coded AWS access keys.
- Writes application logs to stdout/stderr so the CloudWatch Agent can collect them.
- Optional SNS email notification when a student is added.
- Health-check endpoint at `/health`.

## Important limitations
- This is a learning demo, not a production-ready student information system.
- SQLite data is stored on the EC2 filesystem. It is not highly available and can be lost if the instance/storage is deleted. For a more complete project, migrate student records to RDS or DynamoDB.
- The app does not provide authentication, CSRF protection, virus scanning, or production-grade file validation. Do not put real student personal data into this demo.
- S3 objects are private. The app records the S3 object key; it does not make uploaded files publicly accessible.
- The delete action deletes only the student record, not the S3 object.

## 1. Create AWS resources
1. Create a VPC and subnet, route table, and internet access appropriate for your lab.
2. Launch an EC2 instance (Amazon Linux 2023 or Ubuntu) and deploy this project.
3. Create an S3 bucket with Block Public Access enabled.
4. Create an IAM role trusted by EC2 and attach it to the instance. Grant only the permissions needed:
   - `s3:PutObject` on `arn:aws:s3:::YOUR_BUCKET/student-files/*`
   - If you later add downloads/listing, add only the necessary actions and resources.
   - `sns:Publish` on your specific SNS topic ARN if using notifications.
5. Optional: create an SNS Standard topic, subscribe your email, and confirm the subscription.
6. Configure CloudWatch metrics and an alarm. Install/configure the CloudWatch Agent if you want application logs collected.

## 2. Install and run locally for testing
Python 3.10+ is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export AWS_REGION=ap-south-1
export S3_BUCKET=YOUR_BUCKET_NAME
# Optional:
export SNS_TOPIC_ARN=arn:aws:sns:ap-south-1:YOUR_ACCOUNT_ID:student-system-alerts
python app.py
```

Open `http://127.0.0.1:5000`. Local testing requires AWS credentials configured through a secure AWS profile or environment provided by your organization. Do not commit credentials to GitHub.

## 3. Deploy on EC2 (basic lab)
On an Amazon Linux instance, install Python and Git if needed, then clone/copy this project.

```bash
sudo dnf update -y
sudo dnf install -y python3 python3-pip git
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export AWS_REGION=ap-south-1
export S3_BUCKET=YOUR_BUCKET_NAME
export SNS_TOPIC_ARN=YOUR_SNS_TOPIC_ARN
gunicorn --bind 0.0.0.0:8000 app:app
```

For a simple test, allow TCP 8000 from your own IP in the EC2 security group and open `http://EC2_PUBLIC_IP:8000`. For a better deployment, put Nginx or Apache in front of Gunicorn and use HTTPS; do not leave a development server exposed to the internet. Configure environment variables using a protected service configuration, not by committing secrets to the repository.

## 4. Verify S3 upload
1. Open the website.
2. Enter a student name, email, and course.
3. Select an image or PDF and submit.
4. Open S3 → your bucket → `student-files/`. The object should appear if the EC2 role and bucket settings allow the upload.

If upload fails, check:
- EC2 has the correct IAM role attached.
- Role policy permits `s3:PutObject` to the bucket prefix.
- `S3_BUCKET` and `AWS_REGION` are correct.
- The bucket policy or organization policies are not denying the operation.
- Application logs contain the detailed error.

## 5. CloudWatch and SNS
- EC2 basic metrics are available in CloudWatch automatically.
- For application logs, configure the CloudWatch Agent to collect the Gunicorn/app logs.
- Create a CloudWatch alarm on EC2 CPU utilization and select the SNS topic as the alarm action.
- Confirm the SNS email subscription before testing.

## Architecture summary
Student browser → EC2 Flask app → private S3 bucket for uploads.
EC2 metrics/logs → CloudWatch → alarm → SNS email.

For real student data, add authentication, authorization, CSRF protection, robust file validation and malware scanning, HTTPS, backups, and a managed database such as RDS.
