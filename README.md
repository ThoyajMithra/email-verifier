# Email Validator

A simple web application that checks email addresses and shows whether they are likely to be deliverable, undeliverable, or unknown.

You can enter multiple email addresses at once and view the results in a table.

## Features

- Checks email address format.
- Checks whether the domain has MX records.
- Checks SMTP server connectivity.
- Reports whether the mailbox is likely to exist.
- Classifies addresses as deliverable, undeliverable, risky, or unknown.


## How It Works

1. Enter one or more email addresses, with each address on a separate line.
2. Click **Validate Emails**.
3. The backend sends each address to the verification API.
4. The results are displayed in a table.

## Deployment Limitations

Free tire severs block port 25 for smtp requests we have to use Third party API.

The deployed application uses the VerifyAnyEmail API to verify email addresses.

It can check email syntax, MX records, SMTP connectivity, and the provider's assessment of mailbox existence when those results are available.

The application does not connect directly to mail servers to verify mailboxes. Instead, it relies on the third-party API, so the checks available depend on that service.

Some mail servers restrict mailbox verification or hide whether an address exists. Therefore, SMTP connectivity does not guarantee that a mailbox exists, and a deliverable result does not guarantee successful email delivery.

If the verification service cannot determine whether an address exists, the application reports the result as `unknown`.



## Running Locally

1. Install the required packages:

   ```bash
   pip install fastapi uvicorn httpx python-dotenv
   ```

2. Create a `.env` file in the project directory and add your API key:

   ```text
   VAE_API_KEY=your_api_key
   ```

3. Start the backend:

   ```bash
   uvicorn main:app --reload
   ```

   Replace `main` with your Python filename if it is different.

4. Open `index.html` in your browser.

Make sure the frontend's API URL points to the running backend.

## Note

Keep your API key private. Do not commit your `.env` file to GitHub.
