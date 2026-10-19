import os
import logging
import sqlite3
import uuid
from datetime import datetime

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from flask import Flask, render_template, request, redirect, url_for, flash

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "students.db")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-for-real-deployment")

# Logs go to stdout/stderr, which can be collected by the CloudWatch Agent on EC2.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("student-management")

AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")
S3_BUCKET = os.environ.get("S3_BUCKET", "")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")

# Boto3 automatically uses the EC2 instance profile IAM role when deployed on EC2.
s3 = boto3.client("s3", region_name=AWS_REGION)
sns = boto3.client("sns", region_name=AWS_REGION)


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                course TEXT NOT NULL,
                image_key TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


def notify_sns(subject, message):
    if not SNS_TOPIC_ARN:
        return
    try:
        sns.publish(TopicArn=SNS_TOPIC_ARN, Subject=subject[:100], Message=message)
        logger.info("SNS notification published")
    except (BotoCoreError, ClientError):
        logger.exception("Could not publish SNS notification")


@app.route("/", methods=["GET"])
def index():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        students = conn.execute("SELECT * FROM students ORDER BY id DESC").fetchall()
    return render_template("index.html", students=students, bucket_configured=bool(S3_BUCKET))


@app.route("/students", methods=["POST"])
def add_student():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    course = request.form.get("course", "").strip()
    image = request.files.get("image")

    if not name or not email or not course:
        flash("Please enter the student's name, email, and course.", "error")
        return redirect(url_for("index"))

    image_key = None
    if image and image.filename:
        if not S3_BUCKET:
            flash("S3_BUCKET is not configured, so the image was not uploaded.", "error")
            return redirect(url_for("index"))

        # Generate a safe, unique object key rather than trusting the uploaded filename.
        extension = os.path.splitext(image.filename)[1].lower()
        allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf"}
        if extension not in allowed_extensions:
            flash("Allowed file types: JPG, JPEG, PNG, GIF, WEBP, PDF.", "error")
            return redirect(url_for("index"))

        image_key = f"student-files/{uuid.uuid4().hex}{extension}"
        try:
            s3.upload_fileobj(
                image,
                S3_BUCKET,
                image_key,
                ExtraArgs={"ContentType": image.mimetype or "application/octet-stream"}
            )
            logger.info("Uploaded file to S3: bucket=%s key=%s", S3_BUCKET, image_key)
        except (BotoCoreError, ClientError):
            logger.exception("S3 upload failed")
            flash("The file could not be uploaded to S3. Check IAM permissions and bucket settings.", "error")
            return redirect(url_for("index"))

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "INSERT INTO students (name, email, course, image_key, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, email, course, image_key, datetime.utcnow().isoformat(timespec="seconds") + "Z")
        )
        student_id = cursor.lastrowid
        conn.commit()

    logger.info("Student created: id=%s", student_id)
    notify_sns("New student added", f"Student record {student_id} was added to the Student Management System.")
    flash("Student added successfully. Any uploaded file was saved to S3.", "success")
    return redirect(url_for("index"))


@app.route("/students/<int:student_id>/delete", methods=["POST"])
def delete_student(student_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        if row is None:
            flash("Student not found.", "error")
            return redirect(url_for("index"))
        conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
        conn.commit()

    # This demo keeps file deletion separate to avoid accidental document loss.
    logger.info("Student deleted: id=%s", student_id)
    flash("Student record deleted. Its S3 file, if any, was not deleted.", "success")
    return redirect(url_for("index"))


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200


init_db()

if __name__ == "__main__":
    # For local testing only. For production, use a production WSGI server such as Gunicorn.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
