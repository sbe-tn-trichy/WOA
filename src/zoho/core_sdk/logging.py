import logging
import os

_SERVICE_LOGGERS = {
    "books": (("zoho.books.api", "zoho_books_api.log"), ("zoho_books", "zoho_books_api.log")),
    "inventory": (("zoho_inventory", "zoho_inventory_api.log"),),
    "wd": (("zoho.wd.api", "zoho_wd_api.log"), ("zoho.wd.app", "app.log"), ("zoho_wd.app", "app.log")),
    "mail": (("zoho_mail", "zoho_mail_api.log"),),
    "sheet": (("zoho_sheet", "zoho_sheet_api.log"),),
    "creator": (("zoho_creator", "zoho_creator_api.log"),),
    "cliq": (("zoho_cliq", "zoho_cliq_api.log"),),
}


def configure_service_logger(service_name: str) -> logging.Logger:
    """Configure a service's primary logger and its compatibility loggers."""
    configs = _SERVICE_LOGGERS.get(service_name)
    if configs is None:
        return logging.getLogger(f"zoho.{service_name}")

    logger = configure_logger(*configs[0])
    for name, filename in configs[1:]:
        configure_logger(name, filename)
    return logger


def configure_logger(logger_name: str, log_filename: str) -> logging.Logger:
    """
    Configures a logger with a FileHandler in the tests/logs or logs directory,
    ensuring it is done dynamically without import-time side-effects.
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    # Allow users to disable automated file logging
    if os.environ.get("ZOHO_DISABLE_FILE_LOGGING") == "true":
        return logger

    if not logger.handlers:
        project_root = os.environ.get("PROJECT_ROOT", os.getcwd())
        is_testing = "PYTEST_CURRENT_TEST" in os.environ or os.getenv("TESTING") == "true"
        log_dir = os.path.join(project_root, "tests" if is_testing else "", "logs")
        
        try:
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, log_filename)
            
            # Use appropriate formatting depending on type of logger
            if "app" in logger_name:
                formatter = logging.Formatter('%(asctime)s - [APP] [ZOHO_WD] %(levelname)s - [%(funcName)s] - %(message)s')
            elif "api" in logger_name:
                formatter = logging.Formatter('%(asctime)s - [API] %(levelname)s - %(message)s')
            else:
                formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
                
            file_handler = logging.FileHandler(log_path, encoding='utf-8')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception:
            # Gracefully ignore if we cannot write logs to the filesystem (e.g. read-only system)
            pass
            
    return logger
