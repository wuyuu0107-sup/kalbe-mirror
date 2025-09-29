from django.test import TestCase
from django.contrib.auth.hashers import make_password
from authentication.forms import LoginForm, RegistrationForm
from authentication.models import User
from django import forms


class LoginFormTest(TestCase):
    
    def setUp(self):
        #Set up test data
        self.test_user = User.objects.create(
            username="testuser",
            password=make_password("TestPass123"),
            email="test@example.com",
            display_name="Test User",
            is_verified=True
        )
    
    def test_valid_login_form(self):
        #Test form with valid data
        form_data = {
            'username': 'testuser',
            'password': 'TestPass123'
        }
        form = LoginForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_empty_username(self):
        #Test form validation with empty username
        form_data = {
            'username': '',
            'password': 'TestPass123'
        }
        form = LoginForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
        self.assertEqual(form.errors['username'][0], 'Username is required.')
    
    def test_empty_password(self):
        #Test form validation with empty password
        form_data = {
            'username': 'testuser',
            'password': ''
        }
        form = LoginForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)
        self.assertEqual(form.errors['password'][0], 'Password is required.')
    
    def test_username_max_length(self):
        #Test username maximum length validation
        long_username = 'a' * 151  # Exceeds max_length of 150
        form_data = {
            'username': long_username,
            'password': 'TestPass123'
        }
        form = LoginForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
        self.assertEqual(form.errors['username'][0], 'Username must be 150 characters or less.')
    
    def test_username_invalid_characters(self):
        #Test username with invalid characters
        form_data = {
            'username': 'test@user!',
            'password': 'TestPass123'
        }
        form = LoginForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
        self.assertEqual(form.errors['username'][0], 'Username can only contain letters, numbers, dots, hyphens, and underscores.')
    
    def test_username_valid_characters(self):
        #Test username with valid characters
        valid_usernames = ['test_user', 'test-user', 'test.user', 'testuser123']
        for username in valid_usernames:
            form_data = {
                'username': username,
                'password': 'TestPass123'
            }
            form = LoginForm(data=form_data)
            # Note: This will fail authentication but username validation should pass
            self.assertTrue(form.is_valid() or 'username' not in form.errors)
    
    def test_password_min_length(self):
        #Test password minimum length validation
        form_data = {
            'username': 'testuser',
            'password': '1234567'  # 7 characters, less than minimum 8
        }
        form = LoginForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)
        self.assertEqual(form.errors['password'][0], 'Password must be at least 8 characters long.')
    
    def test_authenticate_valid_user(self):
        #Test authentication with valid credentials
        form_data = {
            'username': 'testuser',
            'password': 'TestPass123'
        }
        form = LoginForm(data=form_data)
        self.assertTrue(form.is_valid())
        authenticated_user = form.authenticate()
        self.assertIsNotNone(authenticated_user)
        self.assertEqual(authenticated_user.username, 'testuser')
    
    def test_authenticate_invalid_user(self):
        #Test authentication with non-existent user
        form_data = {
            'username': 'nonexistentuser',
            'password': 'TestPass123'
        }
        form = LoginForm(data=form_data)
        self.assertTrue(form.is_valid())  # Form validation passes
        authenticated_user = form.authenticate()
        self.assertIsNone(authenticated_user)  # But authentication fails
    
    def test_authenticate_wrong_password(self):
        #Test authentication with wrong password
        form_data = {
            'username': 'testuser',
            'password': 'WrongPassword123'
        }
        form = LoginForm(data=form_data)
        self.assertTrue(form.is_valid())  # Form validation passes
        authenticated_user = form.authenticate()
        self.assertIsNone(authenticated_user)  # But authentication fails
    
    def test_authenticate_invalid_form(self):
        #Test authentication with invalid form data
        form_data = {
            'username': '',
            'password': 'TestPass123'
        }
        form = LoginForm(data=form_data)
        self.assertFalse(form.is_valid())
        authenticated_user = form.authenticate()
        self.assertIsNone(authenticated_user)
    
    def test_empty_username_specific_message(self):
        #Test specific validation message for empty username
        form_data = {
            'username': None,  # None value to trigger specific validation
            'password': 'TestPass123'
        }
        form = LoginForm(data=form_data)
        self.assertFalse(form.is_valid())
        # This will trigger the clean_username method

    def test_empty_password_specific_message(self):
        #Test specific validation message for empty password
        form_data = {
            'username': 'testuser',
            'password': None  # None value to trigger specific validation
        }
        form = LoginForm(data=form_data)
        self.assertFalse(form.is_valid())
        # This will trigger the clean_password method
    
    def test_direct_clean_methods_coverage(self):
        """Test direct calls to clean methods for coverage"""
        form = LoginForm()
        
        # Test clean_username with empty string
        form.cleaned_data = {'username': ''}
        with self.assertRaises(forms.ValidationError):
            form.clean_username()
            
        # Test clean_password with empty string  
        form.cleaned_data = {'password': ''}
        with self.assertRaises(forms.ValidationError):
            form.clean_password()


class RegistrationFormTest(TestCase):
    #Test cases for RegistrationForm
    
    def setUp(self):
        """Set up test data"""
        self.existing_user = User.objects.create(
            username="existinguser",
            password=make_password("ExistingPass123"),
            email="existing@example.com",
            display_name="Existing User"
        )
    
    def test_valid_registration_form(self):
        """Test form with valid data"""
        form_data = {
            'username': 'newuser',
            'password': 'NewPass123',
            'confirm_password': 'NewPass123',
            'display_name': 'New User',
            'email': 'new@example.com',
            'roles': []
        }
        form = RegistrationForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_username_required(self):
        #Test username is required
        form_data = {
            'username': '',
            'password': 'NewPass123',
            'confirm_password': 'NewPass123',
            'display_name': 'New User',
            'email': 'new@example.com'
        }
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
        self.assertEqual(form.errors['username'][0], 'Username is required.')
    
    def test_username_min_length(self):
        #Test username minimum length validation
        form_data = {
            'username': 'ab',  # Less than 3 characters
            'password': 'NewPass123',
            'confirm_password': 'NewPass123',
            'display_name': 'New User',
            'email': 'new@example.com'
        }
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
        self.assertEqual(form.errors['username'][0], 'Username must be at least 3 characters long.')
    
    def test_username_already_exists(self):
        #Test username uniqueness validation
        form_data = {
            'username': 'existinguser',  # This username already exists
            'password': 'NewPass123',
            'confirm_password': 'NewPass123',
            'display_name': 'New User',
            'email': 'new@example.com'
        }
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
        self.assertEqual(form.errors['username'][0], 'This username is already taken.')
    
    def test_username_invalid_characters(self):
        #Test username with invalid characters
        form_data = {
            'username': 'new@user!',
            'password': 'NewPass123',
            'confirm_password': 'NewPass123',
            'display_name': 'New User',
            'email': 'new@example.com'
        }
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
        self.assertEqual(form.errors['username'][0], 'Username can only contain letters, numbers, dots, hyphens, and underscores.')
    
    def test_email_required(self):
        #Test email is required
        form_data = {
            'username': 'newuser',
            'password': 'NewPass123',
            'confirm_password': 'NewPass123',
            'display_name': 'New User',
            'email': ''
        }
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertEqual(form.errors['email'][0], 'Email is required.')
    
    def test_email_invalid_format(self):
        #Test email format validation
        invalid_emails = ['invalid', 'invalid@', '@invalid.com', 'invalid.com']
        for email in invalid_emails:
            form_data = {
                'username': 'newuser',
                'password': 'NewPass123',
                'confirm_password': 'NewPass123',
                'display_name': 'New User',
                'email': email
            }
            form = RegistrationForm(data=form_data)
            self.assertFalse(form.is_valid())
            self.assertIn('email', form.errors)
    
    def test_email_already_exists(self):
        #Test email uniqueness validation
        form_data = {
            'username': 'newuser',
            'password': 'NewPass123',
            'confirm_password': 'NewPass123',
            'display_name': 'New User',
            'email': 'existing@example.com'  # This email already exists
        }
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertEqual(form.errors['email'][0], 'This email is already registered.')
    
    def test_password_required(self):
        #Test password is required
        form_data = {
            'username': 'newuser',
            'password': '',
            'confirm_password': 'NewPass123',
            'display_name': 'New User',
            'email': 'new@example.com'
        }
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)
        self.assertEqual(form.errors['password'][0], 'Password is required.')
    
    def test_password_min_length(self):
        #Test password minimum length validation
        form_data = {
            'username': 'newuser',
            'password': '1234567',  # Less than 8 characters
            'confirm_password': '1234567',
            'display_name': 'New User',
            'email': 'new@example.com'
        }
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)
        self.assertEqual(form.errors['password'][0], 'Password must be at least 8 characters long.')
    
    def test_password_uppercase_requirement(self):
        #Test password uppercase letter requirement
        form_data = {
            'username': 'newuser',
            'password': 'newpass123',  # No uppercase letter
            'confirm_password': 'newpass123',
            'display_name': 'New User',
            'email': 'new@example.com'
        }
        form = RegistrationForm(data=form_data)
        self.assertIn('password', form.errors)
        self.assertEqual(form.errors['password'][0], 'Password must contain at least one uppercase letter.')
    
    def test_password_lowercase_requirement(self):
        #Test password lowercase letter requirement
        form_data = {
            'username': 'newuser',
            'password': 'NEWPASS123',  # No lowercase letter
            'confirm_password': 'NEWPASS123',
            'display_name': 'New User',
            'email': 'new@example.com'
        }
        form = RegistrationForm(data=form_data)
        self.assertIn('password', form.errors)
        self.assertEqual(form.errors['password'][0], 'Password must contain at least one lowercase letter.')
    
    def test_password_number_requirement(self):
        #Test password number requirement
        form_data = {
            'username': 'newuser',
            'password': 'NewPassword',  # No number
            'confirm_password': 'NewPassword',
            'display_name': 'New User',
            'email': 'new@example.com'
        }
        form = RegistrationForm(data=form_data)
        self.assertIn('password', form.errors)
        self.assertEqual(form.errors['password'][0], 'Password must contain at least one number.')
    
    def test_password_confirmation_required(self):
        #Test password confirmation is required
        form_data = {
            'username': 'newuser',
            'password': 'NewPass123',
            'confirm_password': '',
            'display_name': 'New User',
            'email': 'new@example.com'
        }
        form = RegistrationForm(data=form_data)
        self.assertIn('confirm_password', form.errors)
        self.assertEqual(form.errors['confirm_password'][0], 'Password confirmation is required.')
    
    def test_password_confirmation_mismatch(self):
        #Test password confirmation mismatch validation
        form_data = {
            'username': 'newuser',
            'password': 'NewPass123',
            'confirm_password': 'DifferentPass123',
            'display_name': 'New User',
            'email': 'new@example.com'
        }
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)
        self.assertEqual(form.errors['__all__'][0], 'Passwords do not match.')
    
    def test_display_name_required(self):
        #Test display name is required
        form_data = {
            'username': 'newuser',
            'password': 'NewPass123',
            'confirm_password': 'NewPass123',
            'display_name': '',
            'email': 'new@example.com'
        }
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('display_name', form.errors)
        msg = form.errors['display_name'][0].lower()
        self.assertTrue('display' in msg and 'name' in msg)
    
    def test_display_name_max_length(self):
        #Test display name maximum length validation
        long_display_name = 'a' * 151  # Exceeds max_length of 150
        form_data = {
            'username': 'newuser',
            'password': 'NewPass123',
            'confirm_password': 'NewPass123',
            'display_name': long_display_name,
            'email': 'new@example.com'
        }
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('display_name', form.errors)
        self.assertEqual(form.errors['display_name'][0], 'Display name must be 150 characters or less.')
    
    def test_roles_optional(self):
        #Test that roles field is optional
        form_data = {
            'username': 'newuser',
            'password': 'NewPass123',
            'confirm_password': 'NewPass123',
            'display_name': 'New User',
            'email': 'new@example.com'
            # No roles field
        }
        form = RegistrationForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_roles_with_valid_data(self):
        #Test roles field with valid JSON data
        form_data = {
            'username': 'newuser',
            'password': 'NewPass123',
            'confirm_password': 'NewPass123',
            'display_name': 'New User',
            'email': 'new@example.com',
            'roles': ['researcher', 'admin']
        }
        form = RegistrationForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    # Additional tests to improve coverage
    def test_username_empty_validation(self):
        #Test username empty validation in RegistrationForm
        form_data = {
            'username': None,
            'password': 'ValidPass123!',
            'confirm_password': 'ValidPass123!',
            'display_name': 'Test User',
            'email': 'test@example.com'
        }
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        
    def test_username_too_short(self):
        #Test username minimum length validation
        form_data = {
            'username': 'ab',  # Only 2 characters
            'password': 'ValidPass123!',
            'confirm_password': 'ValidPass123!',
            'display_name': 'Test User',
            'email': 'test@example.com'
        }
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        
    def test_username_entirely_numeric(self):
        #Test username entirely numeric validation
        form_data = {
            'username': '123456',  # All numbers
            'password': 'ValidPass123!',
            'confirm_password': 'ValidPass123!',
            'display_name': 'Test User',
            'email': 'test@example.com'
        }
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        
    def test_username_invalid_start_end(self):
        #Test username starting/ending with dots or underscores
        for username in ['.testuser', '_testuser', 'testuser.', 'testuser_']:
            form_data = {
                'username': username,
                'password': 'ValidPass123!',
                'confirm_password': 'ValidPass123!',
                'display_name': 'Test User',
                'email': 'test@example.com'
            }
            form = RegistrationForm(data=form_data)
            self.assertFalse(form.is_valid())
            
    def test_email_required_validation(self):
        #Test email required validation
        form_data = {
            'username': 'testuser',
            'password': 'ValidPass123!',
            'confirm_password': 'ValidPass123!',
            'display_name': 'Test User',
            'email': None
        }
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        
    def test_password_empty_validation(self):
        #Test password empty validation in RegistrationForm
        form_data = {
            'username': 'testuser',
            'password': None,
            'confirm_password': 'ValidPass123!',
            'display_name': 'Test User',
            'email': 'test@example.com'
        }
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        
    def test_display_name_xss_characters(self):
        #Test display name XSS character validation
        invalid_names = ['User<script>', 'User"quote', 'User/slash', 'User\\backslash', 'User>tag']
        for name in invalid_names:
            form_data = {
                'username': 'testuser',
                'password': 'ValidPass123!',
                'confirm_password': 'ValidPass123!',
                'display_name': name,
                'email': 'test@example.com'
            }
            form = RegistrationForm(data=form_data)
            self.assertFalse(form.is_valid())
            
    def test_clean_method_password_mismatch(self):
        #Test the clean() method for password mismatch
        form_data = {
            'username': 'testuser',
            'password': 'ValidPass123!',
            'confirm_password': 'DifferentPass123!',
            'display_name': 'Test User',
            'email': 'test@example.com'
        }
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)  # Non-field errors
        self.assertIn('Passwords do not match', str(form.errors['__all__']))
    
    def test_direct_registration_clean_methods_coverage(self):
        #Test direct calls to clean methods for additional coverage
        form = RegistrationForm()
        
        # Test clean_username with empty string
        form.cleaned_data = {'username': ''}
        with self.assertRaises(forms.ValidationError):
            form.clean_username()
            
        # Test clean_username with short username
        form.cleaned_data = {'username': 'ab'}
        with self.assertRaises(forms.ValidationError):
            form.clean_username()
            
        # Test clean_email with empty email
        form.cleaned_data = {'email': ''}
        with self.assertRaises(forms.ValidationError):
            form.clean_email()
            
        # Test clean_password with empty password
        form.cleaned_data = {'password': ''}
        with self.assertRaises(forms.ValidationError):
            form.clean_password()
            
        # Test clean_password without uppercase letter
        form.cleaned_data = {'password': 'nouppercase123!'}  # Fixed: no uppercase
        with self.assertRaises(forms.ValidationError) as cm:
            form.clean_password()
        self.assertIn("Password must contain at least one uppercase letter", str(cm.exception))
            
        # Test clean_display_name with XSS characters
        for char in ['<', '>', '"', '/', '\\']:
            form.cleaned_data = {'display_name': f'User{char}test'}
            with self.assertRaises(forms.ValidationError) as cm:
                form.clean_display_name()
            self.assertIn("Display name cannot contain", str(cm.exception))
    
    def test_specific_coverage_targets(self):
        #Specific tests to hit the exact missing lines
        
        # Target line 163: Password uppercase validation
        form_data = {
            'username': 'testuser',
            'password': 'lowercase123!',  # No uppercase letters
            'confirm_password': 'lowercase123!',
            'display_name': 'Test User',
            'email': 'test@example.com'
        }
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)
        
        # Target line 179: Display name XSS validation  
        form_data = {
            'username': 'testuser',
            'password': 'ValidPass123!',
            'confirm_password': 'ValidPass123!', 
            'display_name': 'User<script>alert("xss")</script>',  # Contains < and >
            'email': 'test@example.com'
        }
        form = RegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('display_name', form.errors)
    
    def test_direct_method_calls_for_100_percent_coverage(self):
        #Direct method calls to ensure we hit lines 163 and 179
        
        # Create form instance for direct method testing
        reg_form = RegistrationForm()
        
        reg_form.cleaned_data = {'password': 'alllowercase123!'}  # No uppercase
        with self.assertRaises(forms.ValidationError) as cm:
            reg_form.clean_password()
        self.assertIn("uppercase letter", str(cm.exception))
        
        reg_form.cleaned_data = {'display_name': 'User<xss>'}  # Contains < and >
        with self.assertRaises(forms.ValidationError) as cm:
            reg_form.clean_display_name()
        self.assertIn("cannot contain", str(cm.exception))

    def test_direct_clean_password_min_length(self):
        """Directly test password min length branch in clean_password"""
        reg_form = RegistrationForm()
        # password shorter than 8 should raise the specific ValidationError
        reg_form.cleaned_data = {'password': '1234567'}
        with self.assertRaises(forms.ValidationError) as cm:
            reg_form.clean_password()
        self.assertIn('at least 8 characters', str(cm.exception))

    def test_direct_clean_display_name_whitespace(self):
        """Directly test display_name whitespace-only is rejected"""
        reg_form = RegistrationForm()
        reg_form.cleaned_data = {'display_name': '   '}
        with self.assertRaises(forms.ValidationError) as cm:
            reg_form.clean_display_name()
        # exact message expected from the form
        self.assertIn('A display name is required', str(cm.exception))