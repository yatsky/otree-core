# -*- coding: utf-8 -*-

import threading
import time
import urllib

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.http import (
    HttpResponse, HttpResponseRedirect, Http404, HttpResponseNotFound
)

import vanilla

import otree.constants as constants
from otree.views.abstract import GenericWaitPageMixin
from otree.session.models import Session
from otree.session import (
    create_session, get_session_types_dict, get_session_types_list
)
from otree.common_internal import (
    get_session_module, get_models_module, app_name_format
)

import otree.adminlib

def start_link_url(session_type_name):
    return '/demo/{}/'.format(session_type_name)


class DemoIndex(vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r'^demo/$'

    def get(self, *args, **kwargs):

        intro_text = getattr(get_session_module(), 'demo_page_intro_text', '')

        session_info = []
        for session_type in get_session_types_list(demo_only=True):
            session_info.append(
                {
                    'name': session_type.name,
                    'display_name': session_type.display_name,
                    'url': start_link_url(session_type.name),
                    'num_demo_parcitipants': session_type.num_demo_participants
                }
            )
        return TemplateResponse(
            self.request, 'otree/demo/index.html',
            {
                'session_info': session_info, 'intro_text': intro_text,
                'debug': settings.DEBUG
            }
        )


def ensure_enough_spare_sessions(session_type_name):

    time.sleep(5)

    DESIRED_SPARE_SESSIONS = 3

    spare_sessions = Session.objects.filter(
        special_category=constants.session_special_category_demo,
        session_type_name=session_type_name,
        demo_already_used=False,
    ).count()

    # fill in whatever gap exists. want at least 3 sessions waiting.
    for i in range(DESIRED_SPARE_SESSIONS - spare_sessions):
        create_session(
            special_category=constants.session_special_category_demo,
            session_type_name=session_type_name,
            preassign_players_to_groups=True,
        )


def get_session(session_type_name):

    sessions = Session.objects.filter(
        special_category=constants.session_special_category_demo,
        session_type_name=session_type_name,
        demo_already_used=False,
        ready=True,
    )
    if sessions.exists():
        return sessions[:1].get()


def sort_links(links):
    """Return the sorted .items() result from a dictionary

    """
    return sorted(links.items())


def keywords_links(keywords):
    """Create a duckduckgo.com link for every keyword

    """
    links = []
    for kw in keywords:
        kw = kw.strip()
        if kw:
            args = urllib.urlencode({"q": kw + " game theory", "t": "otree"})
            link = "https://duckduckgo.com/?{}".format(args)
            links.append((kw, link))
    return links


def info_about_session_type(session_type):

    subsession_apps = []
    seo = set()
    for app_name in session_type.subsession_apps:
        models_module = get_models_module(app_name)
        num_rounds = models_module.Constants.number_of_rounds
        formatted_app_name = app_name_format(app_name)
        if num_rounds > 1:
            formatted_app_name = '{} ({} rounds)'.format(
                formatted_app_name, num_rounds
            )
        subsssn = {
            'doc': getattr(models_module, 'doc', ''),
            'source_code': getattr(models_module, 'source_code', ''),
            'bibliography': getattr(models_module, 'bibliography', []),
            'links': sort_links(getattr(models_module, 'links', {})),
            'keywords': keywords_links(getattr(models_module, 'keywords', [])),
            'name': formatted_app_name,
        }
        seo.update(map(lambda (a, b): a, subsssn["keywords"]))
        subsession_apps.append(subsssn)
    return {
        'doc': session_type.doc,
        'subsession_apps': subsession_apps,
        'page_seo': seo
    }


def render_to_start_links_page(request, session):
    from otree.views.concrete import AdvanceSession

    experimenter_url = request.build_absolute_uri(
        session.session_experimenter._start_url()
    )
    participant_urls = [
        request.build_absolute_uri(participant._start_url())
        for participant in session.get_participants()
    ]
    context_data = {
        'display_name': session.session_type.display_name,
        'experimenter_url': experimenter_url,
        'participant_urls': participant_urls,
        'advance_session_url': request.build_absolute_uri(AdvanceSession.url(session.code)),
        'session_monitor_url': otree.adminlib.session_monitor_url(session),
    }

    session_type = get_session_types_dict(demo_only=True)[session.session_type_name]
    context_data.update(info_about_session_type(session_type))

    return TemplateResponse(
        request, 'otree/admin/StartLinks.html', context_data
    )


class Demo(GenericWaitPageMixin, vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r"^demo/(?P<session_type>.+)/$"

    def _is_ready(self):
        session = get_session(self.session_type_name)
        return bool(session)

    def _before_returning_wait_page(self):
        session_types = get_session_types_dict(demo_only=True)
        try:
            session_types[self.session_type_name]
        except KeyError:
            msg = (
                "Session type '{}' not found, or not enabled for demo"
            ).format(self.session_type_name)
            return HttpResponseNotFound(msg)


        t = threading.Thread(
            target=ensure_enough_spare_sessions,
            args=(self.session_type_name,)
        )
        t.start()

    def body_text(self):
        return 'Creating a session'

    def _response_when_ready(self):
        session = get_session(self.session_type_name)
        session.demo_already_used = True
        session.save()

        return render_to_start_links_page(
            self.request, session
        )

    def dispatch(self, request, *args, **kwargs):
        self.session_type_name=kwargs['session_type']
        return super(Demo, self).dispatch(request, *args, **kwargs)

    def _get_wait_page(self):
        return TemplateResponse(self.request, 'otree/WaitPage.html', {'view': self})