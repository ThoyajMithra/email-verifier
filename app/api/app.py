import os
import asyncio

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

VAE_API_KEY = os.getenv("VAE_API_KEY")
VAE_API_URL = "https://api.verifyany.email/v1/verify"

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


async def verify_with_api(client: httpx.AsyncClient, email: str):
    try:
        response = await client.post(
            VAE_API_URL,
            headers={
                "Authorization": f"Bearer {VAE_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"email": email},
        )

        print(f"API status for {email}: {response.status_code}")

        response.raise_for_status()
        data = response.json()

        if not data.get("ok") or "result" not in data:
            return {
                "email": email,
                "status": "unknown",
                "message": "The verification API returned no result.",
                "result": None,
            }

        result = data["result"]
        status = result.get("status", "unknown")

        messages = {
            "deliverable": "The provider classified the address as deliverable.",
            "undeliverable": "The provider classified the address as undeliverable.",
            "risky": "The address has risk indicators.",
            "unknown": "The address could not be verified conclusively.",
        }

        return {
            "email": email,
            "status": status if status in messages else "unknown",
            "message": messages.get(status, messages["unknown"]),
            "result": result,
        }

    except httpx.HTTPStatusError as e:
        print(
            f"HTTP error for {email}: "
            f"{e.response.status_code} - {e.response.text}"
        )

        return {
            "email": email,
            "status": "unknown",
            "message": f"Verification API returned HTTP {e.response.status_code}.",
            "result": None,
        }

    except (httpx.HTTPError, ValueError) as e:
        print(f"Request error for {email}: {type(e).__name__}: {e}")

        return {
            "email": email,
            "status": "unknown",
            "message": "The verification service could not complete the request.",
            "result": None,
        }


@app.post("/api/process")
async def process(data: RequestData):
    if not VAE_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="VAE_API_KEY is not configured.",
        )

    async with httpx.AsyncClient(timeout=30.0) as client:
        results = await asyncio.gather(
            *(verify_with_api(client, email) for email in data.emails)
        )

    return {
        "results": results,
        "count": len(results),
        "message": "Email validation completed.",
    }