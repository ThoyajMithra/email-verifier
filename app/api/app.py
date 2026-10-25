from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.api.verify_email import verify_email_async

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RequestData(BaseModel):
    emails: list[str] = Field(min_length=1, max_length=100)


@app.post("/api/process")
async def process(data: RequestData):
    results = await verify_email_async(
        data.emails,
        timeout=10,
        verify=True,
    )

    # Normalize a single result to a list.
    if not isinstance(results, list):
        results = [results]

    response = []

    for email, result in zip(data.emails, results):
        if result is True:
            status = "likely_deliverable"
            message = "The mail server accepted the recipient."
        elif result is False:
            status = "likely_to_bounce"
            message = "The address failed one or more validation checks."
        else:
            status = "unknown"
            message = "The address could not be verified conclusively."

        response.append({
            "email": email,
            "status": status,
            "message": message,
        })

    return {
        "results": response,
        "count": len(response),
        "message": "Email validation completed."
    }
