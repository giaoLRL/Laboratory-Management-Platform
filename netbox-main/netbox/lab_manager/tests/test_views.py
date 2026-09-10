"""视图与接口测试：404/405、日历参数容错、媒体鉴权、打卡去重、导入并发。"""
import io
import json

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from lab_manager.models import (
    AgentTool, CheckInRecord, Hardware, HardwareBorrowRecord, HardwareImportBatch, Task,
)

PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489'
    '0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082'
)


class ErrorHandlingTests(TestCase):
    """回归：缺失对象曾返回 500，评论视图 GET 曾 500。"""

    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username='admin3', password='x', is_superuser=True,
        )
        self.task = Task.objects.create(title='t', description='d', created_by=self.admin,
                                        assigned_to=self.admin)

    def test_missing_object_returns_404(self):
        self.client.force_login(self.admin)
        for url in [
            reverse('plugins:lab_manager:borrow_return', args=[999999]),
            reverse('plugins:lab_manager:notification_read', args=[999999]),
            reverse('plugins:lab_manager:task_complete', args=[999999]),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_task_comment_get_returns_405(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('plugins:lab_manager:task_comment', args=[self.task.pk]))
        self.assertEqual(response.status_code, 405)

    def test_calendar_tolerates_bad_year(self):
        self.client.force_login(self.admin)
        for query in ['?year=abc', '?year=99999', '?year=', '?year=2026&month=99']:
            with self.subTest(query=query):
                response = self.client.get(reverse('plugins:lab_manager:calendar') + query)
                self.assertEqual(response.status_code, 200)

    def test_notifications_read_all_requires_post(self):
        self.client.force_login(self.admin)
        url = reverse('plugins:lab_manager:notification_read_all')
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 302)


class MediaPermissionTests(TestCase):
    """回归：插件上传目录曾对任意登录用户开放。"""

    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='owner', password='x')
        self.other = get_user_model().objects.create_user(username='other', password='x')
        CheckInRecord.objects.create(
            user=self.owner, photo='checkins/photos/secret.jpg',
            latitude=1, longitude=1,
        )

    def test_anonymous_is_redirected(self):
        response = self.client.get('/media/checkins/photos/secret.jpg')
        self.assertIn(response.status_code, (302, 404))

    def test_non_owner_gets_404(self):
        self.client.force_login(self.other)
        response = self.client.get('/media/checkins/photos/secret.jpg')
        self.assertEqual(response.status_code, 404)

    def test_superuser_is_allowed(self):
        root = get_user_model().objects.create_user(username='root', password='x', is_superuser=True)
        self.client.force_login(root)
        # 文件本身不存在时由 serve() 返回 404；关键是不能被权限检查提前拦下
        # （超管走的是与普通成员不同的分支，这里仅确认请求被正常处理而非报错）
        response = self.client.get('/media/checkins/photos/secret.jpg')
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'does not exist', status_code=404)


class CheckInTests(TestCase):
    """回归：同一用户短时间内重复提交会产生多条打卡记录。"""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username='checkin_user', password='x')

    def _post_checkin(self):
        photo = SimpleUploadedFile('p.png', PNG, content_type='image/png')
        return self.client.post(reverse('plugins:lab_manager:checkin_create'), {
            'photo': photo, 'latitude': '39.9042', 'longitude': '116.4074',
            'accuracy': '10', 'address': '测试地址', 'note': 'QA',
        })

    def test_duplicate_submit_is_ignored(self):
        self.client.force_login(self.user)
        self._post_checkin()
        self._post_checkin()
        self.assertEqual(CheckInRecord.objects.filter(user=self.user).count(), 1)


class HardwareImportCommitTests(TestCase):
    """回归：重复提交会重复入库，非法数据曾被静默写入。"""

    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username='admin4', password='x', is_superuser=True,
        )
        self.client.force_login(self.admin)
        self.url = reverse('plugins:lab_manager:agent_hardware_import_commit')

    def _batch(self, items):
        return HardwareImportBatch.objects.create(
            created_by=self.admin, source_type='json', status='validated',
            validated_payload={'valid_items': items},
        )

    def test_commit_then_duplicate_is_rejected(self):
        batch = self._batch([{'name': '导入硬件', 'category': 'mcu', 'quantity': 1}])
        payload = {'import_action': 'commit', 'confirm': True, 'batch_id': batch.batch_id}

        first = self.client.post(self.url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(first.status_code, 200)
        second = self.client.post(self.url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(second.status_code, 409)
        self.assertEqual(Hardware.objects.filter(name='导入硬件').count(), 1)

    def test_invalid_item_rolls_back_whole_batch(self):
        batch = self._batch([
            {'name': '合法硬件', 'category': 'mcu', 'quantity': 1},
            {'name': '非法硬件', 'category': '不存在的类别', 'quantity': 1},
        ])
        response = self.client.post(
            self.url,
            data=json.dumps({'import_action': 'commit', 'confirm': True, 'batch_id': batch.batch_id}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 422)
        self.assertFalse(Hardware.objects.filter(name='合法硬件').exists())
        batch.refresh_from_db()
        self.assertNotEqual(batch.status, 'imported')


class AgentApiInputTests(TestCase):
    """回归：非对象 JSON、非法过滤条件曾直接 500。"""

    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username='admin5', password='x', is_superuser=True,
        )
        self.client.force_login(self.admin)

    def test_non_object_json_returns_400(self):
        response = self.client.post(
            reverse('plugins:lab_manager:agent_hardware_search'),
            data='[]', content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_date_filter_returns_400(self):
        response = self.client.post(
            reverse('plugins:lab_manager:agent_platform_query'),
            data=json.dumps({'model': 'hardware', 'filters': {'created__gte': 'abc'}}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_requirements_item_type_returns_400(self):
        response = self.client.post(
            reverse('plugins:lab_manager:agent_hardware_gap_analysis'),
            data=json.dumps({'requirements': ['开发板']}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
