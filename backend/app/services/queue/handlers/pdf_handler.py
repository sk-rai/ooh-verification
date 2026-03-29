"""generate_pdf task handler."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.queue.registry import task_handler
import logging

logger = logging.getLogger(__name__)


@task_handler("generate_pdf")
async def handle_generate_pdf(db: AsyncSession, payload: dict):
    """Generate a PDF report in the background."""
    from app.services.report_generator import ReportGenerator
    from app.services.chart_generator import ChartGenerator
    from app.services.map_generator import MapGenerator
    from app.services.pdf_generator import PDFGenerator

    campaign_code = payload["campaign_code"]
    tenant_id = payload.get("tenant_id")

    chart_gen = ChartGenerator()
    map_gen = MapGenerator()
    report_gen = ReportGenerator(db, chart_gen, map_gen, tenant_id=tenant_id)

    stats = await report_gen.get_campaign_statistics(campaign_code)
    campaign_data = stats["campaign"]

    chart_images = {}
    for chart_type in ["verification", "confidence", "timeline"]:
        try:
            chart_images[chart_type] = await report_gen.generate_chart_data(
                campaign_code, chart_type, "png"
            )
        except Exception as e:
            logger.warning(f"Chart {chart_type} generation failed: {e}")
            chart_images[chart_type] = None

    pdf_gen = PDFGenerator()
    pdf_bytes = pdf_gen.generate_campaign_report(
        campaign_data=campaign_data,
        statistics=stats,
        chart_images=chart_images,
    )

    # Store PDF bytes — for now we log completion. 
    # In future, store to Cloudinary or a temp file and update a report_jobs record.
    logger.info(f"Generated PDF for campaign {campaign_code}: {len(pdf_bytes)} bytes")
