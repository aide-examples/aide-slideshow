"""
Application-specific utilities for the slideshow.

This package contains utilities specific to this application,
as opposed to aide_frame which contains reusable framework code.

Contents:
- helpers: Welcome image generation, documentation, image preparation
- app_config: Application-specific configuration defaults
"""

from .helpers import (
    PathSecurityError, resolve_safe_path, load_static_file, load_readme,
    list_docs, load_doc, extract_title, extract_title_and_description,
    get_docs_structure, url_to_filename, generate_welcome_image,
    get_or_create_welcome_image, get_imgPrepare, ImagePrepareJob, prepare_job
)

from .app_config import DEFAULT_CONFIG

__all__ = [
    # helpers
    'PathSecurityError', 'resolve_safe_path', 'load_static_file', 'load_readme',
    'list_docs', 'load_doc', 'extract_title', 'extract_title_and_description',
    'get_docs_structure', 'url_to_filename', 'generate_welcome_image',
    'get_or_create_welcome_image', 'get_imgPrepare', 'ImagePrepareJob', 'prepare_job',
    # config
    'DEFAULT_CONFIG',
]
