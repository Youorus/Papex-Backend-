from rest_framework.test import APIClient
from api.users.models import User
from api.users.roles import UserRoles

def test_endpoints():
    print("Testing endpoints...")
    client = APIClient(HTTP_HOST='127.0.0.1')
    
    # Create or get an admin user
    admin_user, _ = User.objects.get_or_create(
        email="admin_test_stats@papex.fr",
        defaults={
            "first_name": "Admin",
            "last_name": "Test",
            "role": UserRoles.ACCUEIL,
            "is_active": True,
            "is_superuser": True,
        }
    )
    admin_user.set_password("password123")
    admin_user.save()
    
    client.force_authenticate(user=admin_user)
    
    # Get a creator ID
    from api.creators.models import CreatorProfile
    creator = CreatorProfile.objects.first()
    creator_id = str(creator.id) if creator else "42411512-ccf3-4f61-875a-9b9220d43a01"
    
    endpoints = [
        '/api/creators/stats/',
        '/api/creators/aggregate-kpis/',
        f'/api/creators/{creator_id}/kpis/',
        '/api/promo-codes/',
        '/api/creator-contracts/',
    ]
    
    for endpoint in endpoints:
        print(f"\nTesting {endpoint}...")
        response = client.get(endpoint)
        print(f"Status Code: {response.status_code}")
        if response.status_code != 200:
            print("Response Error:")
            print(response.content.decode()[:1000])
        else:
            print("Response Data:")
            print(response.json())

test_endpoints()
