from django.shortcuts import get_object_or_404
from drf_extra_fields.fields import Base64ImageField
from rest_framework import serializers

from users.models import User
from food.models import AmountIngredient, Ingredient, Recipe, Tag


class UserSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'email', 'id', 'username', 'first_name',
            'last_name', 'is_subscribed'
        )

    def get_is_subscribed(self, obj):
        if self.context['request'].user.is_authenticated:
            return obj.following.filter(
                user=self.context['request'].user
            ).exists()
        return False

    def validate(self, data):
        if data.get('username') == 'me':
            raise serializers.ValidationError(
                'Username указан неверно!')
        return data

    def create(self, validated_data):
        return User.objects.create_user(
            **validated_data, password=self.initial_data['password']
        )


class FollowSerializer(UserSerializer):
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'email', 'id', 'username', 'first_name',
            'last_name', 'is_subscribed', 'recipes', 'recipes_count'
        )

    def get_recipes(self, obj):
        recipes_limit = (
            self.context['request'].query_params.get('recipes_limit')
        )
        recipes = obj.recipes.all()
        if recipes_limit is not None:
            recipes_limit = int(recipes_limit)
            serializer = SmallRecipeSerializer(
                recipes[:recipes_limit], many=True
            )
        else:
            serializer = SmallRecipeSerializer(recipes, many=True)
        return serializer.data

    def get_recipes_count(self, obj):
        return obj.recipes.count()


class PasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(max_length=150)
    current_password = serializers.CharField(max_length=150)


class TagSerializer(serializers.ModelSerializer):

    class Meta:
        model = Tag
        fields = ('id', 'name', 'color', 'slug')


class IngredientSerializer(serializers.ModelSerializer):

    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class FullAmountIngredientSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='ingredient.id')
    name = serializers.CharField(source='ingredient.name')
    measurement_unit = serializers.CharField(
        source='ingredient.measurement_unit'
    )

    class Meta:
        model = AmountIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class AmountIngredientSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField()

    class Meta:
        model = AmountIngredient
        fields = ('id', 'amount')


class SmallRecipeSerializer(serializers.ModelSerializer):

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class FullRecipeSerializer(serializers.ModelSerializer):
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    image = Base64ImageField()
    author = UserSerializer(read_only=True)
    tags = TagSerializer(read_only=True, many=True)
    ingredients = FullAmountIngredientSerializer(read_only=True, many=True)

    class Meta:
        model = Recipe
        fields = (
            'id', 'tags', 'author', 'ingredients',
            'is_favorited', 'is_in_shopping_cart', 'name',
            'image', 'text', 'cooking_time'
        )

    def get_is_favorited(self, obj):
        if (
            self.context['request'].user.is_authenticated
            and obj.favorite_recipes.filter(
                user=self.context['request'].user
            ).exists()
        ):
            return True
        return False

    def get_is_in_shopping_cart(self, obj):
        if (
            self.context['request'].user.is_authenticated
            and obj.shopping_list_recipes.filter(
                user=self.context['request'].user
            ).exists()
        ):
            return True
        return False


class RecordRecipeSerializer(FullRecipeSerializer):
    tags = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all()
    )
    ingredients = AmountIngredientSerializer(many=True)

    class Meta:
        model = Recipe
        fields = (
            'id', 'tags', 'author', 'ingredients',
            'is_favorited', 'is_in_shopping_cart', 'name',
            'image', 'text', 'cooking_time'
        )

    def taking_validated_data(self, validated_data):
        queryset_tags = validated_data.pop('tags')
        ingredients = validated_data.pop('ingredients')
        queryset_amount_ingredients = []
        for new_ingredient in ingredients:
            ingredient = get_object_or_404(
                Ingredient,
                pk=new_ingredient['id']
            )
            amount_ingredient, created = (
                AmountIngredient.objects.get_or_create(
                    ingredient=ingredient,
                    amount=new_ingredient['amount']
                )
            )
            if created:
                amount_ingredient.save()
            queryset_amount_ingredients.append(amount_ingredient)
        return queryset_tags, queryset_amount_ingredients

    def create(self, validated_data):
        author = self.context['request'].user
        queryset_tags, queryset_amount_ingredients = (
            self.taking_validated_data(validated_data)
        )
        recipe = Recipe.objects.create(
            **validated_data,
            author=author
        )
        recipe.tags.set(queryset_tags)
        recipe.ingredients.set(queryset_amount_ingredients)
        return recipe

    def update(self, instance, validated_data):
        ingredients = validated_data.pop('ingredients')
        tags = validated_data.pop('tags')
        instance.image = validated_data.get('image', instance.image)
        instance.name = validated_data.get('name', instance.name)
        instance.text = validated_data.get('text', instance.text)
        instance.cooking_time = validated_data.get('cooking_time',
                                                   instance.cooking_time)
        instance.tags.clear()
        instance.ingredients.clear()
        for tag in tags:
            instance.tags.add(tag)
        for item in ingredients:
            current_ingredient = item.get('ingredient')
            amount = item.get('amount')
            ingredient_amount, _ = AmountIngredient.objects.get_or_create(
                ingredient=current_ingredient,
                amount=amount
            )
            instance.ingredients.add(ingredient_amount)
        instance.save()
        return instance

    def validate_ingredients(self, data):
        ingredients = self.initial_data.get('ingredients')
        ingredients_list = {}
        if ingredients:
            for ingredient in ingredients:
                if ingredient.get('id') in ingredients_list:
                    raise serializers.ValidationError(('Повтор ингредиента!'))
                ingredients_list[ingredient.get('id')] = (
                    ingredients_list.get('amount')
                )
        return data
