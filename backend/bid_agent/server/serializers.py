"""Serializers that validate JSON bodies through the existing models."""
import json

from pydantic import BaseModel, ValidationError
from rest_framework import serializers


class PydanticBodySerializer(serializers.Serializer):
    """Adapt a domain model to a serializer without a second schema."""

    model = None

    def to_internal_value(self, data):
        if data in (None, ''):
            data = {}
        if not isinstance(data, dict):
            raise serializers.ValidationError('请求体必须是 JSON 对象')
        try:
            return self.model.model_validate(data)
        except ValidationError as exc:
            raise serializers.ValidationError({
                'detail': json.loads(exc.json()),
            }) from exc

    def to_representation(self, instance):
        if isinstance(instance, BaseModel):
            return instance.model_dump(mode='json')
        return instance


def serializer_for(model):
    """Build a serializer class bound to one domain model."""
    name = f'{model.__name__}Serializer'
    return type(name, (PydanticBodySerializer,), {'model': model})
