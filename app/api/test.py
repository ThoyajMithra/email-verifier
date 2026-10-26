from datetime import datetime
from verify_email import verify_email
import multiprocessing


emails = ["thoyajmithra17@gmail.com"]


def validate(email):
    start = datetime.now()

    try:
        value = verify_email(email, timeout=10, debug=True)
    except Exception as exc:
        value = f"ERROR: {type(exc).__name__}: {exc}"

    elapsed = (datetime.now() - start).total_seconds()

    print(f"Email: {email}")
    print(f"Result: {value}")
    print(f"Time: {elapsed:.3f} seconds")

    return value


if __name__ == "__main__":

    with multiprocessing.Pool(processes=2) as pool:
        results = pool.map(validate, emails)

