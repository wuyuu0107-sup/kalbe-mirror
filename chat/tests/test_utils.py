from unittest.mock import patch, Mock, MagicMock
from types import SimpleNamespace as NS
import os
import sys
import uuid
import json

from authentication.models import User
from django.urls import reverse
from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from chat.models import ChatSession
