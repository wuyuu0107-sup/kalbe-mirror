# from django.test import TestCase
# from authentication.models import User
# from rest_framework.test import APITestCase
# from rest_framework import status
# from datetime import datetime
# from dashboard.models import ChatSuggestion


# class ChatSuggestionModelTest(TestCase):
    
#     def setUp(self):

#         ChatSuggestion.objects.all().delete()

#         self.user = User.objects.create(
#             username='testuser',
#             password='testpass123',
#             display_name='Test User',
#             email='testuser@example.com',
#             is_verified=True
#         )
    
#     def test_create_chat_suggestion(self):
        
#         suggestion = ChatSuggestion.objects.create(
#             user=self.user,
#             title="Test Suggestion",
#             content="This is a test suggestion content"
#         )
        
#         self.assertEqual(suggestion.title, "Test Suggestion")
#         self.assertEqual(suggestion.content, "This is a test suggestion content")
#         self.assertEqual(suggestion.user, self.user)
#         self.assertIsNotNone(suggestion.created_at)
#         self.assertIsNotNone(suggestion.updated_at)
    
#     def test_chat_suggestion_string_representation(self):
        
#         suggestion = ChatSuggestion.objects.create(
#             user=self.user,
#             title="Test Title",
#             content="Test content"
#         )
        
#         self.assertEqual(str(suggestion), "Test Title")
    
#     def test_chat_suggestion_ordering(self):
#         """Test that suggestions are ordered by created_at descending"""
        
#         suggestion1 = ChatSuggestion.objects.create(
#             user=self.user,
#             title="First",
#             content="First content"
#         )
#         suggestion2 = ChatSuggestion.objects.create(
#             user=self.user,
#             title="Second",
#             content="Second content"
#         )
        
#         suggestions = ChatSuggestion.objects.all()
#         self.assertEqual(suggestions[0], suggestion2)
#         self.assertEqual(suggestions[1], suggestion1)


# class ChatSuggestionAPITest(APITestCase):
#     """Test API endpoints"""

#     def setUp(self):
#         User.objects.all().delete()
#         ChatSuggestion.objects.all().delete()

#         self.user = User.objects.create(
#             username='testuser',
#             password='testpass123',
#             display_name='Test User',
#             email='testuser@example.com',
#             is_verified=True
#         )

#         self.client.force_authenticate(user=self.user)

#         self.other_user = User.objects.create(
#             username='otheruser',
#             password='testpass123',
#             display_name='Other User',
#             email='otheruser@example.com',
#             is_verified=True
#         )
    
#     def test_create_chat_suggestion(self):
#         """Test create chat suggestion via API"""
#         url = '/api/chat-suggestions/'
#         data = {
#             'title': 'New Suggestion',
#             'content': 'This is my suggestion content'
#         }
        
#         response = self.client.post(url, data, format='json')
        
#         self.assertEqual(response.status_code, status.HTTP_201_CREATED)
#         self.assertEqual(response.data['title'], 'New Suggestion')
#         self.assertEqual(response.data['content'], 'This is my suggestion content')
#         self.assertEqual(response.data['user'], str(self.user.user_id))  # UUID as string
    
#     def test_create_chat_suggestion_without_authentication(self):
#         """Test unauthenticated users cannot create suggestions"""
#         self.client.force_authenticate(user=None)
#         url = '/api/chat-suggestions/'
#         data = {
#             'title': 'New Suggestion',
#             'content': 'This is my suggestion content'
#         }
        
#         response = self.client.post(url, data, format='json')
        
#         self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    
#     def test_list_chat_suggestions(self):
#         """Test listing all chat suggestions for authenticated user"""
        
#         ChatSuggestion.objects.create(user=self.user, title="Suggestion 1", content="Content 1")
#         ChatSuggestion.objects.create(user=self.user, title="Suggestion 2", content="Content 2")
#         ChatSuggestion.objects.create(user=self.other_user, title="Other Suggestion", content="Other Content")
        
#         url = '/api/chat-suggestions/'

#         self.client.force_authenticate(user=self.user)

#         response = self.client.get(url)
        
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(len(response.data), 4)

    
#     def test_retrieve_chat_suggestion(self):
#         """Test retrieve a specific chat suggestion"""
  
#         suggestion = ChatSuggestion.objects.create(
#             user=self.user,
#             title="Test Suggestion",
#             content="Test Content"
#         )
        
#         url = f'/api/chat-suggestions/{suggestion.id}/'
#         response = self.client.get(url)
        
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(response.data['title'], 'Test Suggestion')
#         self.assertEqual(response.data['content'], 'Test Content')
    
#     def test_update_chat_suggestion(self):
#         """Test update a chat suggestion"""

#         suggestion = ChatSuggestion.objects.create(
#             user=self.user,
#             title="Original Title",
#             content="Original Content"
#         )
        
#         url = f'/api/chat-suggestions/{suggestion.id}/'
#         data = {
#             'title': 'Updated Title',
#             'content': 'Updated Content'
#         }
        
#         response = self.client.put(url, data, format='json')
        
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(response.data['title'], 'Updated Title')
#         self.assertEqual(response.data['content'], 'Updated Content')
        
#         # Verify update
#         suggestion.refresh_from_db()
#         self.assertEqual(suggestion.title, 'Updated Title')
#         self.assertEqual(suggestion.content, 'Updated Content')
    
#     def test_partial_update_chat_suggestion(self):
#         """Test partially update a chat suggestion"""

#         suggestion = ChatSuggestion.objects.create(
#             user=self.user,
#             title="Original Title",
#             content="Original Content"
#         )
        
#         url = f'/api/chat-suggestions/{suggestion.id}/'
#         data = {
#             'title': 'Updated Title Only'
#         }
        
#         response = self.client.patch(url, data, format='json')
        
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(response.data['title'], 'Updated Title Only')
#         self.assertEqual(response.data['content'], 'Original Content')
    
#     def test_delete_chat_suggestion(self):
#         """Test delete a chat suggestion"""

#         suggestion = ChatSuggestion.objects.create(
#             user=self.user,
#             title="To Be Deleted",
#             content="Delete this"
#         )
        
#         url = f'/api/chat-suggestions/{suggestion.id}/'
#         response = self.client.delete(url)
        
#         self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
#         # Verify deletion
#         self.assertFalse(ChatSuggestion.objects.filter(id=suggestion.id).exists())
    
#     def test_cannot_update_other_users_suggestion(self):
#         """Test that users cannot update other users' suggestions"""

#         suggestion = ChatSuggestion.objects.create(
#             user=self.other_user,
#             title="Other User's Suggestion",
#             content="Other Content"
#         )
        
#         url = f'/api/chat-suggestions/{suggestion.id}/'
#         data = {
#             'title': 'Hacked Title',
#             'content': 'Hacked Content'
#         }
        
#         response = self.client.put(url, data, format='json')
        
#         self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
#     def test_cannot_delete_other_users_suggestion(self):
#         """Test that users cannot delete other users' suggestions"""
        
#         suggestion = ChatSuggestion.objects.create(
#             user=self.other_user,
#             title="Other User's Suggestion",
#             content="Other Content"
#         )
        
#         url = f'/api/chat-suggestions/{suggestion.id}/'
#         response = self.client.delete(url)
        
#         self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
#         # Verify not deleted
#         self.assertTrue(ChatSuggestion.objects.filter(id=suggestion.id).exists())
    
#     def test_title_required(self):
#         """Test title is required"""
#         url = '/api/chat-suggestions/'
#         data = {
#             'content': 'Content without title'
#         }
        
#         response = self.client.post(url, data, format='json')
        
#         self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
#         self.assertIn('title', response.data)
    
#     def test_content_required(self):
#         """Test content is required"""
#         url = '/api/chat-suggestions/'
#         data = {
#             'title': 'Title without content'
#         }
        
#         response = self.client.post(url, data, format='json')
        
#         self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
#         self.assertIn('content', response.data)