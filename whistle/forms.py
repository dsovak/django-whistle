import re

from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Div, HTML, Field, Layout, Submit
from django import forms
from django.utils.translation import ugettext_lazy as _, ugettext

from whistle.managers import NotificationManager
from whistle.models import Notification
from whistle import settings as whistle_settings


class NotificationAdminForm(forms.ModelForm):
    class Meta:
        model = Notification
        exclude = ()

    def clean(self):
        event = self.cleaned_data.get('event', None)

        if event is not None:
            event_display = dict(whistle_settings.EVENTS).get(event)
            error = _('This field is required for selected event.')

            ctx_mapping = {
                'object_id': 'object',
                'target_id': 'target',
                'actor': 'actor',
            }

            for field, variable in ctx_mapping.items():
                value = self.cleaned_data.get(field, None)
                if value is None and '%({})s'.format(variable) in event_display:
                    self.add_error(field, error)

        return self.cleaned_data


class NotificationSettingsForm(forms.Form):
    def __init__(self, user, *args, **kwargs):
        super(NotificationSettingsForm, self).__init__(*args, **kwargs)
        self.user = user
        self.init_fields()
        self.init_form_helper()

    @property
    def labels(self):
        events = dict(whistle_settings.EVENTS)

        for event, label in events.items():
            pat = re.compile(r'%\(.*\)s|"%\(.*\)s"|%\(.*\)r|"%\(.*\)r"')
            new_label = re.sub(pat, '', ugettext(label))  # remove all variable placeholders
            new_label = new_label.replace("''", '')  # remove all 2 single quotas
            new_label = new_label.replace('""', '')  # remove all 2 double quotas
            new_label = new_label.strip(' :.')  # remove trailing spaces and semicolons
            new_label = re.sub(' +', ' ', new_label)  # remove all multiple spaces

            events[event] = new_label

        return events

    def field_names(self, event):
        event_identifier = event.lower()

        return {
            'web': 'web_{}'.format(event_identifier),
            'email': 'email_{}'.format(event_identifier),
            'push': 'push_{}'.format(event_identifier)
        }

    def get_initial_value(self, channel, event=None):
        return NotificationManager.is_notification_enabled(self.user, channel, event, bypass_channel=True)

    def init_fields(self):
        self.fields.update({
            'web': forms.BooleanField(label=_('Web'), required=False, initial=self.get_initial_value('web')),
            'email': forms.BooleanField(label=_('E-mail'), required=False, initial=self.get_initial_value('web')),
            'push': forms.BooleanField(label=_('Push'), required=False, initial=self.get_initial_value('web'))
        })

        for event, label in self.labels.items():
            field_names = self.field_names(event)

            self.fields.update({
                field_names['web']: forms.BooleanField(label=_('Web'), required=False, initial=self.get_initial_value('web', event)),
                field_names['email']: forms.BooleanField(label=_('E-mail'), required=False, initial=self.get_initial_value('email', event)),
                field_names['push']: forms.BooleanField(label=_('Push'), required=False, initial=self.get_initial_value('push', event))
            })

    def init_form_helper(self):
        fields = []

        channel_fields = []

        for channel in whistle_settings.CHANNELS:
            if NotificationManager.is_notification_available(self.user, channel):
                channel_fields.append(
                    Div(Field(channel, css_class='switch'), css_class='channel fw-bold col-md mb-3')
                )

        fields.append(Div(
                Div(HTML('<p>{}</p>'.format(_(''))), css_class='col-md'),
                *channel_fields,
                css_class='row'
            )
        )

        for event, label in self.labels.items():
            field_names = self.field_names(event)
            event_fields = []

            for channel in whistle_settings.CHANNELS:
                if NotificationManager.is_notification_available(self.user, channel, event):
                    event_fields.append(
                        Div(Field(field_names[channel], css_class='switch'), css_class='col-md')
                    )

            if len(event_fields) > 0:
                fields.append(Div(
                        Div(HTML('<p>{}</p>'.format(label)), css_class='col-md-6'),
                        *event_fields,
                        css_class='row'
                    )
                )

        fields.append(
            FormActions(
                Submit('submit', _('Save'), css_class='btn-lg')
            )
        )

        self.helper = FormHelper()
        self.helper.form_class = 'notification-settings'
        self.helper.layout = Layout(*fields)

    def clean(self):
        settings = {
            'channels': {
                'web': self.cleaned_data.get('web', True),
                'email': self.cleaned_data.get('email', True),
                'push': self.cleaned_data.get('push', True)
            },
            'events': {
                'email': {},
                'web': {},
                'push': {}
            }
        }

        # events
        for event in self.labels.keys():
            field_names = self.field_names(event)
            event_identifier = event.lower()

            settings['events']['web'][event_identifier] = self.cleaned_data.get(field_names['web'], True)
            settings['events']['email'][event_identifier] = self.cleaned_data.get(field_names['email'], True)
            settings['events']['push'][event_identifier] = self.cleaned_data.get(field_names['push'], True)

        return settings
