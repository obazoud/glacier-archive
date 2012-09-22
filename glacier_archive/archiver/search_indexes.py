from haystack import indexes
#from celery_haystack import indexes as celindexes

import datetime
from archiver.models import Archives,ArchiveFiles


class ArchiveIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True)
    short_description = indexes.CharField(model_attr='short_description',boost=1.2)
    startdate = indexes.DateTimeField(model_attr='startdate')
    tags = indexes.CharField(model_attr='tags',boost=1.2)
    archive_id = indexes.CharField(model_attr='archive_id')

    def get_model(self):
        return Archives

    def index_queryset(self):
        """Used when the entire index for model is updated."""
        return self.get_model().objects.filter(startdate__lte=datetime.datetime.now())

class ArchiveFileIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True)
    filepath = indexes.CharField(model_attr='filepath',boost=1.2)
    startdate = indexes.DateTimeField(model_attr='startdate')
    fileadate = indexes.DateTimeField(model_attr='fileadate')
    filemdate = indexes.DateTimeField(model_attr='filemdate')
    filecdate = indexes.DateTimeField(model_attr='filecdate')

    def get_model(self):
        return ArchiveFiles

    def index_queryset(self):
        """Used when the entire index for model is updated."""
        return self.get_model().objects.filter(startdate__lte=datetime.datetime.now())    