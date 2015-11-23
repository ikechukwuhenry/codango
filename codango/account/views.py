from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect
from django.views.generic import View, TemplateView
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.template.context_processors import csrf
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.template import RequestContext, loader
from account.hash import UserHasher
from emails import SendGrid
from resources.views import CommunityBaseView
from account.forms import LoginForm, RegisterForm, ResetForm, ContactUsForm
from userprofile.models import UserProfile


class IndexView(TemplateView):
    initial = {'key': 'value'}
    template_name = 'account/index.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated():
            messages.add_message(
                request, messages.SUCCESS, 'Welcome back!')
            return redirect(
                '/home',
                context_instance=RequestContext(request)
            )
        return super(IndexView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        context['loginform'] = LoginForm()
        context['registerform'] = RegisterForm()
        return context


class LoginView(IndexView):
    form_class = LoginForm

    def post(self, request, *args, **kwargs):

        if self.request.is_ajax():
            try:
                userprofile = UserProfile.objects.get(
                    social_id=request.POST['id'])
                user = userprofile.get_user()
                user.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, user)
                return HttpResponse("success", content_type='text/plain')
            except UserProfile.DoesNotExist:
                return HttpResponse("register", content_type='text/plain')

        form = self.form_class(request.POST)
        if form.is_valid():
            username = request.POST['username']
            password = request.POST['password']
            user = authenticate(username=username, password=password)
            if not request.POST.get('remember_me'):
                request.session.set_expiry(0)
            if user is not None:
                if user.is_active:
                    login(request, user)
                    messages.add_message(
                        request, messages.SUCCESS, 'Logged in Successfully!')
                    return redirect(
                        '/home',
                        context_instance=RequestContext(request)
                    )
            else:
                messages.add_message(
                    request, messages.ERROR, 'Incorrect username or password!')
                return redirect(
                    '/',
                    context_instance=RequestContext(request)
                )
        else:
            context = super(LoginView, self).get_context_data(**kwargs)
            context['loginform'] = form
            return render(request, self.template_name, context)


class RegisterView(IndexView):
    form_class = RegisterForm

    def post(self, request, **kwargs):
        form = self.form_class(request.POST)
        if form.is_valid():
            new_user = form.save()
            new_user = authenticate(username=request.POST['username'],
                                    password=request.POST['password'])
            login(request, new_user)
            messages.add_message(
                request, messages.SUCCESS, 'Registered Successfully!')
            new_profile = new_user.profile
            new_profile.social_id = request.POST[
                'social_id'] if 'social_id' in request.POST else None
            new_profile.first_name = request.POST[
                'first_name'] if 'first_name' in request.POST else None
            new_profile.last_name = request.POST[
                'last_name'] if 'last_name' in request.POST else None
            new_profile.save()

            return redirect(
                '/user/' + self.request.user.username + '/edit',
                context_instance=RequestContext(request)
            )
        else:
            context = super(RegisterView, self).get_context_data(**kwargs)
            context['registerform'] = form
            return render(request, self.template_name, context)


class ContactUsView(TemplateView):
    form_class = ContactUsForm
    template_name = 'account/contact-us.html'

    def get_context_data(self, **kwargs):
        context = super(ContactUsView, self).get_context_data(**kwargs)
        context['contactusform'] = ContactUsForm()
        return context


class LoginRequiredMixin(object):
    # View mixin which requires that the user is authenticated.

    @method_decorator(login_required(login_url='/'))
    def dispatch(self, request, *args, **kwargs):
        return super(LoginRequiredMixin, self).dispatch(
            request, *args, **kwargs)


class HomeView(LoginRequiredMixin, CommunityBaseView):
    pass


class ForgotPasswordView(TemplateView):
    form_class = ResetForm
    template_name = 'account/forgot-password.html'

    def post(self, request, *args, **kwargs):
        try:
            # get the email inputted
            email_inputted = request.POST.get("email")

            # query the database if that email exists
            user = User.objects.get(email=email_inputted)

            # generate a recovery hash for that user
            user_hash = UserHasher.gen_hash(user)
            user_hash_url = request.build_absolute_uri(
                reverse('reset_password', kwargs={'user_hash': user_hash}))
            hash_email_context = RequestContext(
                request, {'user_hash_url': user_hash_url})

            # compose the email
            email_compose = SendGrid.compose(
                sender='Codango <codango@andela.com>',
                recipient=user.email,
                subject='Codango: Password Recovery',
                text=loader.get_template(
                    'account/forgot-password-email.txt'
                ).render(hash_email_context),
                html=loader.get_template(
                    'account/forgot-password-email.html'
                ).render(hash_email_context),
            )

            # send email
            email_response = SendGrid.send(email_compose)

            # inform the user if mail sent was successful
            context = {
                "email_status": email_response
            }
            return render(
                request,
                'account/forgot-password-status.html',
                context
            )

        except ObjectDoesNotExist:
            messages.add_message(
                request, messages.ERROR,
                'The email specified does not belong to any valid user.')
            return render(request, 'account/forgot-password.html')


class ResetPasswordView(View):

    def get(self, request, *args, **kwargs):
        user_hash = kwargs['user_hash']
        user = UserHasher.reverse_hash(user_hash)

        if user is not None:
            if user.is_active:
                request.session['user_pk'] = user.pk

                context = {
                    "password_reset_form": ResetForm(auto_id=True)
                }
                context.update(csrf(request))
                return render(request, 'account/forgot-password-reset.html', context)
            else:
                messages.add_message(
                    request, messages.ERROR, 'Account not activated!')
                return HttpResponse(
                    'Account not activated!',
                    status_code=403,
                    reason_phrase='You are not allowed to view this content because your account is not activated!'
                )
        else:
            raise Http404("User does not exist")

    def post(self, request, *args, **kwargs):
        password_reset_form = ResetForm(request.POST, auto_id=True)
        new_password = request.POST.get("password")
        if password_reset_form.is_valid():
            try:
                user_pk = request.session['user_pk']
                user = User.objects.get(pk=user_pk)

                user.set_password(new_password)
                user.save()

                messages.add_message(
                    request, messages.INFO,
                    'Your password has been changed successfully!')

                return redirect('/')

            except ObjectDoesNotExist:
                messages.add_message(
                    request, messages.ERROR,
                    'You are not allowed to perform this action!')
                return HttpResponse('Action not allowed!', status_code=403)

        context = {
            "password_reset_form": password_reset_form
        }
        context.update(csrf(request))
        return render(request, 'account/forgot-password-reset.html', context)
