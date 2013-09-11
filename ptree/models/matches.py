from django.db import models
from django.forms import ModelForm
from django import forms
from ptree.templatetags.ptreefilters import currency
import abc

class MatchManager(models.Manager):
    def next_open_match(self, request):
        """Get the next match that is accepting players.
        May raise a StopIteration exception if there are no open matches.
        """
        from ptree.views.abstract import SessionKeys
        matches = super(MatchManager, self).get_query_set().all()
        return (m for m in matches if m.treatment.code == request.session[SessionKeys.treatment_code] and m.is_ready_for_next_player()).next()

class BaseMatch(models.Model):
    """
    Base class for all Matches.
    
    A Match is a particular instance of a game being played,
    and holds the results of that instance, i.e. what the score was, who got paid what.

    "Match" is used in the sense of "boxing match".
    
    Example of a Match: "dictator game between users Alice & Bob, where Alice gave $0.50"

    If a piece of data is specific to a particular player, you should store it in a Player object instead.
    For example, in the Prisoner's Dilemma, each Player has to decide between "Cooperate" and "Compete".
    You should store these on the Player object as player.decision,
    NOT "match.player_1_decision" and "match.player_2_decision".

    The exception is if the game is asymmetric, and player_1_decision and player_2_decision have different data types.
    """

    #: when the game was started
    time_started = models.DateTimeField(auto_now_add = True)

    objects = MatchManager()

    #@abc.abstractmethod
    def is_ready_for_next_player(self):
        """
        Needs to be implemented by child classes.
        Whether the game is ready for another player to be added.
        """
        raise NotImplementedError()

    def is_full(self):
        """
        Whether the match is full (i.e. no more ``Player``s can be assigned).
        """
        return len(self.players()) >= self.treatment.players_per_match

    def is_finished(self):
        """Whether the match is completed."""
        return self.is_full() and [player.is_finished for player in self.players()]

    def players(self):
        """
        Returns the ``Player`` objects in this match.
        Syntactic sugar ``for self.player_set.all()``
        """
        return self.player_set.all()

    
    class Meta:
        abstract = True
        verbose_name_plural = "matches"
