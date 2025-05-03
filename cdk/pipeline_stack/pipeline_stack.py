import os
import aws_cdk as cdk
from constructs import Construct
from aws_cdk import (
    aws_ecr as ecr,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_codedeploy as codedeploy,
    aws_apigatewayv2_alpha as apigwv2,
    aws_apigatewayv2_integrations_alpha as apigw_integrations,
    Duration,
    RemovalPolicy,
    Stack,
)


class PipelineStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ======== 設定変数（ここにまとめる） ========
        
        # Lambda関連
        LAMBDA_MEMORY = 512  # Lambda関数のメモリサイズ(MB)
        LAMBDA_TIMEOUT = 30  # Lambda関数のタイムアウト(秒)
        LAMBDA_MESSAGE = "Hello from CDK !"  # 環境変数
        
        # API Gateway関連
        API_NAME = "LambdaContainerApiPy"  # API名
        API_PATH = "/hello"  # APIパス
        
        # CodeDeploy関連
        APP_NAME = "MyLambdaApplicationPy"  # CodeDeployアプリケーション名
        ALIAS_NAME = "live"  # Lambdaエイリアス名

        # ECRリポジトリ名 (Bootstrapで作成されたもの)
        ECR_REPO_NAME = f"cdk-hnb659fds-container-assets-{cdk.Aws.ACCOUNT_ID}-{cdk.Aws.REGION}"

        # GitHub Actionsから渡されるイメージタグ
        IMAGE_TAG = os.environ.get("IMAGE_TAG", "latest") # 環境変数から取得
        
        # ======== リソース定義 ========
        # --- ECR リポジトリの参照 ---
        repository = ecr.Repository.from_repository_name(
            self, "LambdaEcrRepo",
            repository_name=ECR_REPO_NAME
        )

        # --- Lambda 関数の IAM ロール ---
        lambda_role = iam.Role(
            self, "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
        )

        # --- Lambda 関数 (ECRイメージを参照) ---
        my_function = lambda_.Function(
            self, "MyLambdaFunction",
            code=lambda_.Code.from_ecr_image(
                repository=repository, # リポジトリオブジェクトを渡す
                tag_or_digest=IMAGE_TAG # タグを渡す
                # image_uri は使わない
            ),
            handler=lambda_.Handler.FROM_IMAGE,
            runtime=lambda_.Runtime.FROM_IMAGE,
            role=lambda_role,
            environment={"MESSAGE": LAMBDA_MESSAGE},
            memory_size=LAMBDA_MEMORY,
            timeout=Duration.seconds(LAMBDA_TIMEOUT),
            current_version_options=lambda_.VersionOptions(
                removal_policy=RemovalPolicy.RETAIN,
            )
        )

        # --- Lambda エイリアス (CodeDeployが管理) ---
        alias = lambda_.Alias(
            self, "LiveAlias",
            alias_name=ALIAS_NAME,
            version=my_function.current_version,  # 初期状態では最新バージョンを指す
        )

        # --- CodeDeploy アプリケーション & デプロイグループ ---
        application = codedeploy.LambdaApplication(
            self, "CodeDeployApplication",
            application_name=APP_NAME,
        )

        codedeploy.LambdaDeploymentGroup(
            self, "DeploymentGroup",
            application=application,
            alias=alias,
            deployment_config=codedeploy.LambdaDeploymentConfig.CANARY_10_PERCENT_5_MINUTES,  # カナリアリリース設定
            auto_rollback=codedeploy.AutoRollbackConfig(
                # 必要に応じて自動ロールバック設定
                failed_deployment=True,  # デプロイ失敗時にロールバック
                # deployment_in_alarm=True, # アラーム発報時にロールバック (別途CloudWatch Alarmの設定が必要)
            )
        )

        # --- API Gateway (HTTP API) ---
        http_api = apigwv2.HttpApi(
            self, "MyHttpApi",
            api_name=API_NAME,
            description="API Gateway for Lambda Container (Python CDK)",
            # CORS設定など必要に応じて追加
        )

        http_api.add_routes(
            path=API_PATH,
            methods=[apigwv2.HttpMethod.GET],
            integration=apigw_integrations.HttpLambdaIntegration("LambdaIntegration", alias)
        )

        # --- Outputs ---
        cdk.CfnOutput(self, "LambdaFunctionName", value=my_function.function_name)
        cdk.CfnOutput(self, "LambdaFunctionArn", value=my_function.function_arn)
        cdk.CfnOutput(self, "LambdaLiveAliasArn", value=alias.function_arn)
        cdk.CfnOutput(
            self, "ApiEndpoint",
            value=f"{http_api.url}{API_PATH}" if http_api.url else "NoAPIGateway"
        )