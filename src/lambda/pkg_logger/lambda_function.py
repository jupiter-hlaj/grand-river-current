import json
import datetime

def lambda_handler(event, context):
    try:
        # The body is a JSON string, so we need to parse it
        body = json.loads(event.get('body', '{}'))
        
        log_message = body.get('message', 'No message provided')
        log_details = body.get('details', {})
        
        # Construct a structured log for easy searching in CloudWatch
        structured_log = {
            "timestamp_utc": datetime.datetime.utcnow().isoformat(),
            "action": log_message,
            "details": log_details,
            # Extract some source info if available
            "source_ip": event.get('requestContext', {}).get('http', {}).get('sourceIp'),
            "user_agent": event.get('requestContext', {}).get('http', {}).get('userAgent')
        }
        
        # Print the structured log. This is what CloudWatch captures.
        print(json.dumps(structured_log))
        
        # Respond with success. The frontend doesn't wait for this, but it's good practice.
        return {
            "statusCode": 202, # 202 Accepted is appropriate for fire-and-forget
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            },
            "body": json.dumps({"status": "logged"})
        }

    except Exception as e:
        # If something goes wrong, log the error itself
        print(json.dumps({
            "error": "LoggingFailed",
            "error_message": str(e),
            "raw_body": event.get('body') # Log the raw body for debugging
        }))
        
        # Still return a success-like status so we don't cause frontend errors
        return {
            "statusCode": 202,
             "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            },
            "body": json.dumps({"status": "log_error"})
        }
