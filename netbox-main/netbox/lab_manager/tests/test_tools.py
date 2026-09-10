"""工具链与校验器测试：参数归一化、权限、文件类型、SSRF 防护。"""
import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from lab_manager.models import AgentTool, Hardware
from lab_manager.services.tool_registry import execute_tool
from lab_manager.services.web_search import WebSearchService
from lab_manager.validators import validate_attachment_type, validate_image_type


class _FakeFile:
    def __init__(self, name):
        self.name = name


class ValidatorTests(SimpleTestCase):
    def test_image_type_filter(self):
        validate_image_type(_FakeFile('ok.png'))
        with self.assertRaises(ValidationError):
            validate_image_type(_FakeFile('bad.svg'))

    def test_attachment_type_filter(self):
        validate_attachment_type(_FakeFile('doc.pdf'))
        for name in ('x.html', 'x.svg', 'x.js'):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                validate_attachment_type(_FakeFile(name))


class WebSearchSsrfTests(SimpleTestCase):
    def test_private_targets_are_rejected(self):
        service = WebSearchService()
        for url in ('http://127.0.0.1/x', 'http://localhost/x', 'http://10.0.0.1/',
                    'file:///etc/passwd', 'http://169.254.169.254/latest/meta-data/'):
            with self.subTest(url=url):
                self.assertFalse(service.is_safe_public_url(url))

    def test_public_target_is_allowed(self):
        self.assertTrue(WebSearchService().is_safe_public_url('https://example.com/page'))


class ToolRegistryTests(TestCase):
    """回归：LLM 传 filters_json 时过滤条件曾被静默忽略。"""

    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username='tool_admin', password='x', is_superuser=True,
        )
        self.member = get_user_model().objects.create_user(username='tool_member', password='x')
        Hardware.objects.create(name='在用设备', quantity=1, status='in_use')
        Hardware.objects.create(name='报废设备', quantity=1, status='scrapped')

    def test_filters_json_is_normalized(self):
        raw = execute_tool('platform_query', self.admin, {
            'model': 'hardware', 'action': 'list_records', 'limit': 20,
            'filters_json': json.dumps({'status': 'scrapped'}),
        })
        data = json.loads(raw)
        self.assertEqual(data.get('total'), 1)

    def test_record_id_is_normalized(self):
        hardware = Hardware.objects.first()
        raw = json.loads(execute_tool('platform_query', self.admin, {
            'model': 'hardware', 'action': 'get_record_detail', 'record_id': hardware.pk,
        }))
        self.assertEqual(raw.get('item', {}).get('id'), hardware.pk)

    def test_invalid_json_returns_clear_error(self):
        raw = json.loads(execute_tool('platform_query', self.admin, {
            'model': 'hardware', 'filters_json': '{bad',
        }))
        self.assertFalse(raw.get('ok'))
        self.assertIn('JSON', str(raw.get('error')))

    def test_requires_superuser_is_enforced_for_non_superuser(self):
        tool = AgentTool.objects.create(
            name='super_only', display_name='管理员专用', tool_type='data_query',
            execution_key='find_members', is_enabled=True, requires_superuser=True,
            parameters_schema={}, default_args={},
        )
        self.addCleanup(tool.delete)
        denied = json.loads(execute_tool('find_members', self.member, {}))
        self.assertFalse(denied.get('ok'))
        allowed = json.loads(execute_tool('find_members', self.admin, {}))
        self.assertTrue(allowed.get('ok'))

    def test_find_members_hides_email_from_members(self):
        raw = json.loads(execute_tool('find_members', self.member, {'keyword': 'tool_admin'}))
        members = raw.get('members') or []
        self.assertTrue(members)
        self.assertNotIn('email', members[0])

    def test_find_members_excludes_inactive(self):
        inactive = get_user_model().objects.create_user(username='gone', password='x', is_active=False)
        raw = json.loads(execute_tool('find_members', self.admin, {'keyword': 'gone'}))
        self.assertEqual(raw.get('total'), 0)
        self.assertFalse(inactive.is_active)
