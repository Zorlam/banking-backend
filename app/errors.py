from flask import jsonify
from werkzeug.exceptions import HTTPException

from app.validation import ValidationError


def register_error_handlers(app):
    @app.errorhandler(ValidationError)
    def handle_validation_error(err: ValidationError):
        return jsonify({"error": err.message, "field": err.field}), 400

    @app.errorhandler(HTTPException)
    def handle_http_exception(err: HTTPException):
        return jsonify({"error": err.description}), err.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(err: Exception):
        app.logger.exception("Unhandled exception")
        return jsonify({"error": "Something went wrong. Please try again."}), 500
