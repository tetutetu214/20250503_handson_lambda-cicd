import os
import aws_cdk as cdk
from constructs import Construct
from aws_cdk import (
    aws_ecr as ecr,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_codedeploy as codedeploy,
    # aws_apigatewayv2 はまだ stable ではないため Alpha モジュールを使用
    aws_apigatewayv2_alpha as apigwv2,
    aws_apigatewayv2_integrations_alpha as apigw_integrations,
    Duration,
    RemovalPolicy,
    Stack,
)

class PipelineStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- ECR リポジトリ ---
        repository = ecr.Repository(
            self, "LambdaEcrRepo",
            repository_name="my-lambda-container-repo", # 任意の名前に変更
            removal_policy=RemovalPolicy.DESTROY, # ハンズオン用。本番では RETAIN 推奨
            auto_delete_images=True, # ハンズオン用。リポジトリ削除時にイメージも削除
        )

        # --- Lambda 関数の IAM ロール ---
        lambda_role = iam.Role(
            self, "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
        )

        # --- Lambda 関数 (コンテナイメージ) ---
        # GitHub Actionsから渡されるイメージタグをここで使う想定
        image_tag = os.environ.get("IMAGE_TAG", "latest") # 環境変数から取得、なければ'latest'

        my_function = lambda_.Function(
            self, "MyLambdaFunction",
            # コンテナイメージを指定
            code=lambda_.Code.from_ecr_image(
                repository=repository,
                tag_or_digest=image_tag # Actionsでビルドしたタグを指定
            ),
            # コンテナイメージの場合は以下を指定
            handler=lambda_.Handler.FROM_IMAGE,
            runtime=lambda_.Runtime.FROM_IMAGE,
            role=lambda_role,
            environment={
                "MESSAGE": "Hello from CDK (Python) deployed Lambda!",
            },
            memory_size=512,
            timeout=Duration.seconds(30),
            # CodeDeployが古いバージョンを保持できるように設定
            current_version_options=lambda_.VersionOptions(
                removal_policy=RemovalPolicy.RETAIN, # 古いバージョンを保持
            )
        )

        # --- Lambda エイリアス (CodeDeployが管理) ---
        alias = lambda_.Alias(
            self, "LiveAlias",
            alias_name="live",
            version=my_function.current_version, # 初期状態では最新バージョンを指す
        )

        # --- CodeDeploy アプリケーション & デプロイグループ ---
        application = codedeploy.LambdaApplication(
            self, "CodeDeployApplication",
            application_name="MyLambdaApplicationPy", # 任意の名前に変更
        )

        codedeploy.LambdaDeploymentGroup(
            self, "DeploymentGroup",
            application=application,
            alias=alias,
            deployment_config=codedeploy.LambdaDeploymentConfig.CANARY_10PERCENT_5MINUTES, # カナリアリリース設定
            # deployment_config=codedeploy.LambdaDeploymentConfig.LINEAR_10PERCENT_EVERY_1MINUTE # 段階的リリース
            # deployment_config=codedeploy.LambdaDeploymentConfig.ALL_AT_ONCE # 一括デプロイ
            auto_rollback=codedeploy.AutoRollbackConfig(
                # 必要に応じて自動ロールバック設定
                failed_deployment=True, # デプロイ失敗時にロールバック
                # deployment_in_alarm=True, # アラーム発報時にロールバック (別途CloudWatch Alarmの設定が必要)
            )
        )

        # --- (オプション) API Gateway (HTTP API) ---
        http_api = apigwv2.HttpApi(
            self, "MyHttpApi",
            api_name="LambdaContainerApiPy",
            description="API Gateway for Lambda Container (Python CDK)",
            # CORS設定など必要に応じて追加
        )

        http_api.add_routes(
            path="/hello",
            methods=[apigwv2.HttpMethod.GET],
            integration=apigw_integrations.HttpLambdaIntegration("LambdaIntegration", alias)
        )

        # --- Outputs ---
        cdk.CfnOutput(self, "EcrRepositoryUri", value=repository.repository_uri)
        cdk.CfnOutput(self, "LambdaFunctionName", value=my_function.function_name)
        cdk.CfnOutput(self, "LambdaFunctionArn", value=my_function.function_arn)
        cdk.CfnOutput(self, "LambdaLiveAliasArn", value=alias.function_arn)
        cdk.CfnOutput(
            self, "ApiEndpoint",
            value=f"{http_api.url}hello" if http_api.url else "NoAPIGateway"
        )
