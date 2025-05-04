# AWS Lambda コンテナ CI/CD ハンズオン (GitHub Actions + CDK)

## 1. はじめに

このリポジトリは、GitHub Actions と AWS CDK (Cloud Development Kit) を使用して、コンテナイメージベースの AWS Lambda 関数を自動でビルド・デプロイする CI/CD パイプラインを構築するためのハンズオン手順とコードを提供します。

**目的:**

*   コンテナイメージを利用した Lambda 関数の開発・デプロイフローを理解する。
*   GitHub Actions をトリガーとした自動デプロイ (CI/CD) を体験する。
*   AWS CDK (Python) を用いた Infrastructure as Code (IaC) の基本を学ぶ。
*   CodeDeploy を利用した Lambda のカナリアリリースを体験する。

**最終的な構成:**

*   **ソースコード管理:** GitHub
*   **CI/CD:** GitHub Actions
*   **IaC:** AWS CDK (Python)
*   **コンテナレジストリ:** Amazon ECR (Elastic Container Registry)
*   **実行環境:** AWS Lambda (コンテナイメージ)
*   **デプロイ戦略:** AWS CodeDeploy (カナリアリリース)
*   **API公開 (オプション):** Amazon API Gateway (HTTP API)

## 2. ハンズオン手順

以下の手順に従って、環境構築とデプロイを行います。

### 2.1. 前提

*   **AWS アカウント:** 操作可能な AWS アカウントが必要です。
*   **GitHub アカウント:** GitHub リポジトリを作成・操作できるアカウントが必要です。
*   **実行環境:**
    *   **AWS 準備 (IAM, Bootstrap):** AWS CloudShell の利用を推奨します (管理者権限のある IAM ユーザーでログイン)。
    *   **コード作成・編集:** AWS Cloud9 や VSCode Remote、または本手順で利用した Amazon SageMaker Studio Code Editor などの IDE 環境を想定しています。ローカル PC でも可能ですが、AWS CLI, Node.js, Python, Docker のセットアップが必要です。

### 2.2. AWS での事前準備 (CloudShell 推奨)

1.  **OIDC プロバイダの作成:** GitHub Actions が AWS と連携するための信頼関係を設定します。
    ```bash
    # サムプリントは最新のものを確認してください (手順参照)
    aws iam create-open-id-connect-provider --url https://token.actions.githubusercontent.com --client-id-list sts.amazonaws.com --thumbprint-list <最新のサムプリント> --region <リージョン名>
    ```
2.  **GitHub Actions 用 IAM ロールの作成:** GitHub Actions が Assume Role するための IAM ロールを作成し、必要なポリシーをアタッチします。
    *   信頼ポリシー (`trust-policy.json`) を作成 (アカウントID, GitHubユーザー名/リポジトリ名を指定)。
    *   `aws iam create-role` でロールを作成。
    *   必要な管理ポリシー (`AmazonEC2ContainerRegistryFullAccess`, `AWSLambda_FullAccess`, `AmazonAPIGatewayAdministrator`, `AmazonSSMReadOnlyAccess`, `AWSCloudFormationFullAccess` など) をアタッチ。
    *   CDK Bootstrap ロールへの `sts:AssumeRole` と CloudFormation 実行ロールへの `iam:PassRole` を許可するカスタムポリシーを作成し、アタッチ。
    *(詳細はブログ記事本体の手順 2.2.2. および 2.2.5. を参照)*
3.  **CDK Bootstrap の実行:** CDK がデプロイに必要なリソース (S3, ECR, IAM Role, SSM Parameter) を作成します。
    ```bash
    # リージョンを設定
    export AWS_DEFAULT_REGION=<リージョン名>
    export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    # Node.js と CDK CLI をインストール (バージョンはワークフローと合わせる)
    npm install -g aws-cdk
    # Bootstrap 実行
    cdk bootstrap aws://${AWS_ACCOUNT_ID}/${AWS_DEFAULT_REGION}
    ```
    *(もし Bootstrap が S3 バケット存在エラーで失敗した場合は、CloudFormation `CDKToolkit` スタックと該当 S3 バケットを削除してから再実行)*
4.  **ECR リポジトリポリシーの設定:** GitHub Actions が Bootstrap で作成された ECR リポジトリにイメージをプッシュできるようにポリシーを設定します。
    *   `ecr-policy.json` を作成 (Lambda プル許可 + GitHub Actions プッシュ許可)。
    *   `aws ecr set-repository-policy` でポリシーを設定。
    *(詳細はブログ記事本体の手順 2.2.4. を参照)*

### 2.3. GitHub での準備

1.  **リポジトリの作成:** このハンズオン用の GitHub リポジトリを作成します。
2.  **シークレットの登録:** リポジトリの `Settings` > `Secrets and variables` > `Actions` で、以下のシークレットを登録します。
    *   `AWS_ACCOUNT_ID`: あなたの AWS アカウント ID (12桁)

### 2.4. コードの準備 (SageMaker Studio Code Editor など)

1.  **リポジトリのクローン:** 作成した GitHub リポジトリをローカル環境にクローンします。
2.  **ファイル構成の作成:** ブログ記事の手順 (2.1.2. および 2.4. 以降) に従って、以下のファイルを作成・編集します。
    *   `your-app/.gitignore`
    *   `your-app/app/app.py` (Lambda 関数コード)
    *   `your-app/app/Dockerfile`
    *   `your-app/cdk/app.py` (CDK エントリーポイント)
    *   `your-app/cdk/requirements.txt` (Python 依存関係)
    *   `your-app/cdk/cdk.json` (CDK 設定)
    *   `your-app/cdk/pipeline_stack/__init__.py`
    *   `your-app/cdk/pipeline_stack/pipeline_stack.py` (CDK スタック定義)
        *   **注意:** `ECR_REPO_NAME` 内の Qualifier (`hnb659fds` など) を、手順 2.2.5. で確認した自身の Qualifier に置き換えてください。
    *   `your-app/.github/workflows/deploy.yml` (GitHub Actions ワークフロー)

### 2.5. デプロイと動作確認

1.  **Git Push:** 作成・編集したコードを Git でコミットし、`master` (または `main`) ブランチにプッシュします。
    ```bash
    git add .
    git commit -m "Add application and CDK code"
    git push origin master
    ```
2.  **GitHub Actions の確認:** GitHub リポジトリの `Actions` タブでワークフローが実行され、すべてのステップが成功することを確認します (初回は約2分、2回目以降は約7分かかります)。
3.  **API Gateway エンドポイント URL の取得:** GitHub Actions の `Deploy CDK Stack` のログ、または CloudFormation スタック (`LambdaPipelineStackPy`) の出力から `ApiEndpoint` の URL を取得します。
4.  **動作確認 (`curl`):** ターミナルから `curl` コマンドで取得した URL にアクセスします。
    ```bash
    API_ENDPOINT="<取得したURL>" # 例: https://....execute-api.us-east-1.amazonaws.com/hello
    curl "$API_ENDPOINT"
    ```
5.  **応答確認:** 以下のような JSON 応答が返ってくれば成功です。
    ```json
    {"message":"Hello from CDK !","version_id":"...","aws_request_id":"..."}
    ```

### 2.6. (オプション) コード変更とカナリアリリースの確認

1.  `your-app/cdk/pipeline_stack/pipeline_stack.py` の `LAMBDA_MESSAGE` の値などを変更します。
2.  変更をコミットし、再度プッシュします。
3.  GitHub Actions の完了後、`curl` を実行します。デプロイ直後の5分間は、古いメッセージと新しいメッセージが混在して返ってくることがあります（カナリアリリース）。5分経過すると、新しいメッセージのみが返ってくるようになります。

### 2.7. クリーンアップ

ハンズオンで作成した AWS リソースを削除します。

1.  **CDK スタックの削除:** CloudShell などから CDK プロジェクトの `cdk` ディレクトリに移動し、実行します。
    ```bash
    cd /path/to/your-app/cdk
    cdk destroy LambdaPipelineStackPy
    ```
    *(権限エラーが出る場合は、CloudFormation コンソールから手動削除)*
2.  **CDK Bootstrap 環境の削除:**
    *   CloudFormation コンソールで `CDKToolkit` スタックを削除します。
    *   S3 コンソールで `cdk-<Qualifier>-assets-...` バケットを削除します (空にする必要あり)。
    *   ECR コンソールで `cdk-<Qualifier>-container-assets-...` リポジトリを削除します (空にする必要あり)。
3.  **IAM ロールとポリシーの削除:**
    *   `GitHubAction-AssumeRoleWithAction` ロールを削除します。
    *   作成したカスタムポリシー (`GitHubAction-AssumeCdkRoles` など) を削除します。
4.  **OIDC プロバイダの削除:**
    *   IAM コンソールの ID プロバイダから `token.actions.githubusercontent.com` を削除します。
5.  **GitHub シークレットの削除:** リポジトリ設定から `AWS_ACCOUNT_ID` を削除します。

## 3. トラブルシューティング (発生したエラーのサマリ)

ハンズオン中に発生した主なエラーとその対策です。

| エラー名                                                                 | 現象                                                                                                                                                              | 原因                                                                                                                                                                                             | 最終的な対策                                                                                                                                                                                                                            |
| :----------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `No module named aws_cdk.cli` (GitHub Actions)                           | `pip install` 後、`python -m aws_cdk.cli deploy` でモジュールが見つからない。                                                                                       | Python バージョン不整合、または GitHub Actions 環境での Python パッケージ認識の問題と想定。                                                                                                       | Node.js ベースの CDK CLI (`npm install -g aws-cdk` と `cdk deploy`) を使う方式に変更。                                                                                                                                             |
| `cdk.json: Unexpected token / in JSON at position ...` (GitHub Actions)  | `cdk deploy` 実行時に JSON 構文エラーが発生。                                                                                                                     | `cdk.json` ファイル内に JSON で許可されていないコメント (`// ...`) が含まれていた。                                                                                                               | `cdk.json` ファイルからコメントを削除。                                                                                                                                                                                                |
| `Unsupported feature flag '@aws-cdk/core:enableStackNameDuplicates'`     | `cdk deploy` 実行時にサポートされていない機能フラグのエラーが発生。                                                                                                 | `cdk.json` の `context` に、CDK v1 用の古い機能フラグが含まれていた。                                                                                                                             | `cdk.json` の `context` から `@aws-cdk/core:enableStackNameDuplicates` の行を削除。                                                                                                                                      |
| `handler must be Handler.FROM_IMAGE when using image asset...`           | `lambda_.Function` + `Code.from_asset` で Lambda をデプロイ時にエラー発生。コード上は `handler` 指定があるにも関わらず発生。                                            | CDK CLI と `aws-cdk-lib` のバージョン不一致、または CDK/JSII の内部的なバグの可能性が高い (GitHub Issue #25758 類似)。                                                                         | `lambda_.DockerImageFunction` クラスを使用するようにコードを書き換え。                                                                                                                                                                 |
| `Cannot find asset at /path/to/app` (GitHub Actions)                     | `Code.from_asset()` や `DockerImageCode.from_image_asset()` で指定したアセットパスが見つからない。                                                                   | `cdk deploy` の実行ディレクトリ (`./cdk`) から見たアセット (`app` ディレクトリ) への相対パス指定が間違っていた (`../../app` ではなく `../app`)。                                                    | `pipeline_stack.py` 内のパス指定を正しい相対パス (`"../app"`) に修正。                                                                                                                                                            |
| `SyntaxError: '(' was never closed` (GitHub Actions)                     | `cdk deploy` の Synth 段階で Python 構文エラーが発生。                                                                                                              | `pipeline_stack.py` のコード修正時に括弧の閉じ忘れがあった。                                                                                                                                      | エラー箇所 (`lambda_.DockerImageFunction` の定義) の括弧の対応を確認し、修正。                                                                                                                                                     |
| `AccessDenied: ... ssm:GetParameter on .../cdk-bootstrap/.../version`    | `cdk deploy` 実行時に SSM パラメータへのアクセス拒否エラーが発生。                                                                                                  | GitHub Actions の IAM ロールに、CDK Bootstrap バージョン情報を読み取る権限がなかった。                                                                                                              | `GitHubAction-AssumeRoleWithAction` ロールに `AmazonSSMReadOnlyAccess` ポリシー（または `ssm:GetParameter` 権限）をアタッチ。                                                                                                         |
| `SSM parameter .../cdk-bootstrap/.../version not found.`                 | `cdk deploy` 実行時に Bootstrap バージョン情報が見つからないエラーが発生。                                                                                           | デプロイ対象のアカウント・リージョンで `cdk bootstrap` が実行されていなかった。                                                                                                                    | CloudShell など適切な権限を持つ環境から `cdk bootstrap` を実行。                                                                                                                                                                |
| `AccessDenied: ... cloudformation:DescribeStacks on .../CDKToolkit/*`    | SageMaker ターミナルから `cdk bootstrap` を実行しようとして権限エラーが発生。                                                                                       | SageMaker の実行ロールに CloudFormation を操作する権限がなかった。                                                                                                                                | 管理者権限を持つユーザーで CloudShell から `cdk bootstrap` を実行。                                                                                                                                                             |
| `S3 ... Bucket ... already exists` (`cdk bootstrap` 実行時)              | `cdk bootstrap` 実行時に S3 バケットが既に存在するためエラーが発生。                                                                                                | 以前の Bootstrap が不完全に終了した、または手動で同名バケットが作成されていた。                                                                                                                    | CloudFormation `CDKToolkit` スタック（失敗時）と該当 S3 バケットを削除後、再度 `cdk bootstrap` を実行。                                                                                                                            |
| `Failed to build asset ...` (ビルド成功直後) (GitHub Actions)            | Docker イメージビルド成功直後にアセットビルド失敗のエラーが発生。`-vvv` でも詳細不明。                                                                                 | IAM/ECR ポリシー/Docker 認証など複合要因が考えられたが特定困難。CDK Assets の Docker イメージ処理に関する内部問題の可能性が高い。                                                                 | CDK Assets 利用をやめ、GitHub Actions で `docker build` & `push` を行い、CDK では `from_ecr_image()` でタグを参照する方式に変更。                                                                                                |
| `TypeError: Code.from_ecr_image() got unexpected keyword argument 'image_uri'` | `cdk deploy` の Synth 段階で `from_ecr_image` の引数エラーが発生。                                                                                                  | `from_ecr_image` に存在しない `image_uri` パラメータを指定していた。                                                                                                                             | 正しいパラメータ `repository` と `tag_or_digest` を使うように修正。                                                                                                                                                           |
| `AccessDenied: ... sts:AssumeRole on .../cdk-...-file-publishing-role-...` | `cdk deploy` 実行時に、Bootstrap のファイル公開用ロールへの Assume Role 権限がないエラーが発生。                                                                      | `GitHubAction-AssumeRoleWithAction` ロールに、Bootstrap ロール群への `sts:AssumeRole` 権限がなかった。                                                                                              | Bootstrap ロール群への `sts:AssumeRole` を許可するカスタム IAM ポリシーを作成し、`GitHubAction-AssumeRoleWithAction` ロールにアタッチ。                                                                                             |
| `AccessDenied: ... iam:PassRole on .../cdk-...-cfn-exec-role-...`        | `cdk deploy` 実行時に、CloudFormation 実行ロールへの PassRole 権限がないエラーが発生。                                                                               | `GitHubAction-AssumeRoleWithAction` ロールに、CloudFormation 実行ロールへの `iam:PassRole` 権限がなかった。                                                                                         | CloudFormation 実行ロールへの `iam:PassRole` を許可するカスタム IAM ポリシーを作成し、`GitHubAction-AssumeRoleWithAction` ロールにアタッチ（または既存カスタムポリシーに追加）。                                                            |
| `Source image ...:latest does not exist.` (GitHub Actions - CloudFormation) | CloudFormation が Lambda 関数を作成しようとして、ECR イメージ `:latest` が見つからないエラーが発生。                                                                    | GitHub Actions から CDK へイメージタグ (コミットハッシュ) が環境変数経由で正しく渡されず、CDK コード側でデフォルトの `:latest` が使われてしまっていた。                                                | GitHub Actions の `cdk deploy` で `-c image_tag=<タグ>` (CDK Context) を使いタグを渡し、CDK コード側も `self.node.try_get_context("image_tag")` で受け取るように修正。                                                              |

## 4. まとめ (得られた知見・今後の課題)

### 4.1. 得られた知見

*   CDK と GitHub Actions を組み合わせた CI/CD では、IAM 権限 (OIDC, AssumeRole, PassRole, 各サービス) の設定が重要であり、エラーから必要な権限を特定・追加していく必要がある。
*   CDK Assets (特に Docker イメージ) の処理は便利だが、CI/CD 環境によっては原因不明のエラーが発生する場合があり、その際は Actions 側でビルド/プッシュし、CDK は参照する方式が有効な回避策となる。
*   CDK CLI と CD