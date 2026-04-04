# HTTP API (API Gateway v2) — cheapest option (~$1/million requests).
# Mangum translates the API Gateway payload format to ASGI automatically.

resource "aws_apigatewayv2_api" "backend" {
  name          = "hsa-tracker-backend"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = split(",", var.cors_origins)
    allow_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization"]
    max_age       = 300
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.backend.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.backend.invoke_arn
  payload_format_version = "2.0"
}

# Catch-all route — Mangum + FastAPI handle all routing internally
resource "aws_apigatewayv2_route" "proxy" {
  api_id    = aws_apigatewayv2_api.backend.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.backend.id
  name        = "$default"
  auto_deploy = true
}

# Allow API Gateway to invoke the Lambda function
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.backend.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.backend.execution_arn}/*/*"
}
