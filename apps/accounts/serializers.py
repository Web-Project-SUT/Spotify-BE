from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from . import services
from .models import User


class UserMeSerializer(serializers.ModelSerializer):
    tier = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "display_name",
            "role",
            "status",
            "tier",
            "bio",
            "avatar",
            "birth_date",
            "gender",
            "created_at",
        ]
        read_only_fields = ["id", "username", "role", "status", "tier", "created_at"]


class MeUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = User
        fields = ["display_name", "email", "bio", "password"]

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=["password"])
        return instance


class RegisterListenerSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    display_name = serializers.CharField(max_length=60, required=True)
    accepted_policy = serializers.BooleanField(write_only=True)

    class Meta:
        model = User
        fields = [
            "email",
            "password",
            "display_name",
            "birth_date",
            "gender",
            "accepted_policy",
        ]

    def validate_accepted_policy(self, value):
        if not value:
            raise serializers.ValidationError("You must accept the privacy policy.")
        return value

    def create(self, validated_data):
        return services.register_listener(
            email=validated_data["email"],
            password=validated_data["password"],
            display_name=validated_data["display_name"],
            birth_date=validated_data.get("birth_date"),
            gender=validated_data.get("gender", ""),
            accepted_policy=validated_data["accepted_policy"],
        )


class RegisterArtistSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    stage_name = serializers.CharField(max_length=80)
    portfolio = serializers.URLField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ["email", "password", "stage_name", "portfolio"]

    def create(self, validated_data):
        return services.register_artist(
            email=validated_data["email"],
            password=validated_data["password"],
            stage_name=validated_data["stage_name"],
            portfolio_url=validated_data.get("portfolio", ""),
        )


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserMeSerializer(self.user).data
        return data


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8)
