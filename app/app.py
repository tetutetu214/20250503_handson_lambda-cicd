import json
import os

def handler(event, context):
    # 環境変数からメッセージを取得
    message = os.environ.get('MESSAGE', 'Hello from Lambda Container!')
    print("Received event: " + json.dumps(event, indent=2))
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': message,
            'version_id': context.function_version,
            'aws_request_id': context.aws_request_id
        })
    }