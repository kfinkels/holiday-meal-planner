"""
Jobs router for Holiday Meal Planner API.

Handles job status queries and management for asynchronous processing.
"""

import logging
from typing import Annotated
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, status, Path

from interfaces.api.dependencies import rate_limited, validated_context
from interfaces.api.responses import JobStatusResponse, JobStatus, ProcessingResultResponse
from interfaces.api.routers.process import get_job_storage


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Job Management"])


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status",
    description="Check the status of an asynchronous menu processing job",
    responses={
        404: {"description": "Job Not Found"},
        429: {"description": "Rate Limit Exceeded"}
    }
)
async def get_job_status(
    job_id: Annotated[UUID, Path(description="Job identifier")],
    _: Annotated[None, rate_limited()],
    context: Annotated[dict, validated_context()]
) -> JobStatusResponse:
    """
    Get the status of an asynchronous processing job.

    Args:
        job_id: Unique job identifier
        _: Rate limiting dependency
        context: Request context for logging

    Returns:
        Job status with progress and results

    Raises:
        HTTPException: If job not found
    """
    try:
        logger.debug(f"Checking status for job {job_id}")

        # Get job storage
        job_storage = get_job_storage()
        job_data = job_storage.get(str(job_id))

        if not job_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error_type": "JobNotFound",
                    "message": f"Job {job_id} not found",
                    "suggestion": "Check the job ID and try again"
                }
            )

        # Build response
        response = JobStatusResponse(
            job_id=job_id,
            status=JobStatus(job_data["status"]),
            progress=job_data.get("progress"),
            created_at=job_data["created_at"],
            updated_at=job_data["updated_at"],
            result=job_data.get("result"),
            error=job_data.get("error")
        )

        return response

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        logger.error(f"Error retrieving job status for {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_type": "InternalServerError",
                "message": "Failed to retrieve job status"
            }
        )


@router.delete(
    "/{job_id}",
    summary="Cancel job",
    description="Cancel a queued or running asynchronous processing job",
    responses={
        200: {"description": "Job Cancelled"},
        404: {"description": "Job Not Found"},
        409: {"description": "Job Cannot Be Cancelled"},
        429: {"description": "Rate Limit Exceeded"}
    }
)
async def cancel_job(
    job_id: Annotated[UUID, Path(description="Job identifier")],
    _: Annotated[None, rate_limited()],
    context: Annotated[dict, validated_context()]
) -> dict:
    """
    Cancel an asynchronous processing job.

    Args:
        job_id: Unique job identifier
        _: Rate limiting dependency
        context: Request context for logging

    Returns:
        Cancellation confirmation

    Raises:
        HTTPException: If job not found or cannot be cancelled
    """
    try:
        logger.info(f"Attempting to cancel job {job_id}")

        # Get job storage
        job_storage = get_job_storage()
        job_data = job_storage.get(str(job_id))

        if not job_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error_type": "JobNotFound",
                    "message": f"Job {job_id} not found"
                }
            )

        current_status = JobStatus(job_data["status"])

        # Check if job can be cancelled
        if current_status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error_type": "JobNotCancellable",
                    "message": f"Job {job_id} cannot be cancelled (status: {current_status})",
                    "current_status": current_status.value
                }
            )

        # Update job status to cancelled
        job_data.update({
            "status": JobStatus.CANCELLED,
            "updated_at": datetime.utcnow(),
            "error": "Job cancelled by user request"
        })

        logger.info(f"Job {job_id} cancelled successfully")

        return {
            "job_id": str(job_id),
            "status": "cancelled",
            "message": "Job cancelled successfully",
            "cancelled_at": datetime.utcnow().isoformat()
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_type": "InternalServerError",
                "message": "Failed to cancel job"
            }
        )


@router.get(
    "/",
    summary="List jobs",
    description="List recent jobs for monitoring (admin endpoint)",
    responses={
        200: {"description": "Jobs Listed"},
        429: {"description": "Rate Limit Exceeded"}
    }
)
async def list_jobs(
    limit: int = 10,
    offset: int = 0,
    status_filter: str = None,
    _: Annotated[None, rate_limited()],
    context: Annotated[dict, validated_context()]
) -> dict:
    """
    List recent processing jobs.

    This is primarily for monitoring and debugging purposes.

    Args:
        limit: Maximum number of jobs to return
        offset: Number of jobs to skip
        status_filter: Filter by job status
        _: Rate limiting dependency
        context: Request context for logging

    Returns:
        List of job summaries

    Raises:
        HTTPException: For invalid parameters
    """
    try:
        logger.debug(f"Listing jobs: limit={limit}, offset={offset}, status={status_filter}")

        # Validate parameters
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error_type": "ValidationError",
                    "message": "Limit must be between 1 and 100"
                }
            )

        if offset < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error_type": "ValidationError",
                    "message": "Offset must be non-negative"
                }
            )

        # Validate status filter
        if status_filter and status_filter not in [s.value for s in JobStatus]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error_type": "ValidationError",
                    "message": f"Invalid status filter: {status_filter}",
                    "valid_statuses": [s.value for s in JobStatus]
                }
            )

        # Get job storage
        job_storage = get_job_storage()

        # Filter and sort jobs
        jobs = list(job_storage.values())

        if status_filter:
            jobs = [job for job in jobs if job["status"] == status_filter]

        # Sort by creation time (most recent first)
        jobs.sort(key=lambda x: x["created_at"], reverse=True)

        # Apply pagination
        total_count = len(jobs)
        paginated_jobs = jobs[offset:offset + limit]

        # Build response
        job_summaries = []
        for job in paginated_jobs:
            summary = {
                "job_id": job["job_id"],
                "status": job["status"],
                "created_at": job["created_at"],
                "updated_at": job["updated_at"],
                "progress": job.get("progress", 0.0)
            }

            # Add error if failed
            if job.get("error"):
                summary["error"] = job["error"]

            # Add basic result info if completed
            if job.get("result"):
                result = job["result"]
                summary["result_summary"] = {
                    "processed_items": result.get("processed_items", 0),
                    "failed_items_count": len(result.get("failed_items", [])),
                    "has_timeline": bool(result.get("timeline"))
                }

            job_summaries.append(summary)

        return {
            "jobs": job_summaries,
            "pagination": {
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total_count
            },
            "filters": {
                "status": status_filter
            }
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        logger.error(f"Error listing jobs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_type": "InternalServerError",
                "message": "Failed to list jobs"
            }
        )