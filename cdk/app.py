import os
import aws_cdk as cdk

# スタック定義ファイルをインポート
from pipeline_stack.pipeline_stack import PipelineStack

app = cdk.App()
PipelineStack(app, "LambdaPipelineStackPy", # スタック名
    # 環境変数やAWSアカウント/リージョンをここで指定
    env=cdk.Environment(
        account=os.getenv('AWS_ACCOUNT_ID'),
        region=os.getenv('AWS_DEFAULT_REGION')
    )
)

app.synth()
