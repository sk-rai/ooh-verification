"""
Report Email API - send site visit reports via email.
"""
import io
import csv
import os
import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.core.deps import get_current_client
from app.models.client import Client
from app.middleware.tenant_context import get_current_tenant

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports/email", tags=["report-email"])


class EmailReportRequest(BaseModel):
    recipients: List[str] = Field(..., description="Email addresses")
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: str = Field(..., description="YYYY-MM-DD")


class ReportSettingsRequest(BaseModel):
    enabled: bool = Field(True)
    recipients: List[str] = Field(default_factory=list)
    frequency: str = Field("daily")


async def send_email_with_csv(to_emails, subject, body, csv_content):
    """Send email with CSV attachment via SMTP or log in dev mode."""
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SENDGRID_FROM_EMAIL", "noreply@trustcaptures.com")

    if smtp_host and smtp_user and smtp_pass:
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            from email.mime.base import MIMEBase
            from email import encoders

            msg = MIMEMultipart()
            msg["From"] = "TrustCapture <" + from_email + ">"
            msg["To"] = ", ".join(to_emails)
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            attachment = MIMEBase("application", "octet-stream")
            attachment.set_payload(csv_content.encode())
            encoders.encode_base64(attachment)
            attachment.add_header("Content-Disposition", "attachment; filename=site_visit_report.csv")
            msg.attach(attachment)

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            logger.info("Report email sent to " + str(to_emails))
            return True
        except Exception as e:
            logger.error("SMTP error: " + str(e))
            return False
    else:
        logger.info("[DEV MODE] Would send report to " + str(to_emails))
        print("[DEV] Report email to " + str(to_emails) + ": " + subject)
        return True


@router.post("/send")
async def send_report_email(
    data: EmailReportRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client),
):
    """Send site visit report to specified email addresses."""
    from app.api.site_visits import get_site_visits

    if not data.recipients:
        raise HTTPException(status_code=400, detail="At least one recipient required")

    report = await get_site_visits(
        start_date=data.start_date, end_date=data.end_date,
        campaign_id=None, db=db, client=client
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Campaign", "Code", "Vendor", "ID", "Phone",
                     "Captures", "First", "Last", "Hours", "Distance(km)",
                     "Verified", "Flagged", "Rejected"])
    for row in report["rows"]:
        writer.writerow([
            row["date"], row["campaign_name"], row["campaign_code"],
            row["vendor_name"], row["vendor_id"], row["vendor_phone"],
            row["total_captures"], row["first_capture"], row["last_capture"],
            row["hours_active"], row["distance_km"],
            row["verified"], row["flagged"], row["rejected"],
        ])
    csv_content = output.getvalue()

    subject = "TrustCapture Site Visit Report (" + data.start_date + " to " + data.end_date + ")"
    body = "Site Visit Report\nPeriod: " + data.start_date + " to " + data.end_date + "\nActive Vendors: " + str(report["summary"]["total_vendors_active"]) + "\nTotal Captures: " + str(report["summary"]["total_captures"]) + "\nTotal Distance: " + str(report["summary"]["total_distance_km"]) + " km\n\nSee attached CSV for details."

    success = await send_email_with_csv(data.recipients, subject, body, csv_content)
    if success:
        return {"status": "sent", "recipients": data.recipients, "rows": len(report["rows"])}
    else:
        raise HTTPException(status_code=500, detail="Failed to send email")


@router.get("/settings")
async def get_report_settings(
    request: Request,
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client),
):
    """Get report email settings."""
    result = await db.execute(
        text("SELECT report_settings FROM clients WHERE client_id = :cid"),
        {"cid": str(client.client_id)}
    )
    row = result.fetchone()
    settings = row[0] if row and row[0] else {"enabled": False, "recipients": [], "frequency": "on_demand"}
    return settings


@router.post("/settings")
async def save_report_settings(
    data: ReportSettingsRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    client: Client = Depends(get_current_client),
):
    """Save report email settings."""
    import json
    settings = {"enabled": data.enabled, "recipients": data.recipients, "frequency": data.frequency}
    await db.execute(
        text("UPDATE clients SET report_settings = :settings WHERE client_id = :cid"),
        {"settings": json.dumps(settings), "cid": str(client.client_id)}
    )
    await db.commit()
    return {"status": "saved", "settings": settings}
