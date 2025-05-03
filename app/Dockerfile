# ＡＷＳ公式提供のベースイメージを使用
FROM public.ecr.aws/lambda/python:3.11

# ハンドラコードをコピー
COPY app.py ./

# Lambdaが呼び出すハンドラを指定
CMD [ "app.handler" ]
