from pathlib import Path


class TestWorkspaceMembers:
    async def test_invite_update_and_remove_member(
        self, client, test_user, second_user, test_workspace
    ):
        invite_response = await client.post(
            f"/api/workspaces/{test_workspace['id']}/members/invite",
            json={"email": second_user["email"], "role": "member"},
            headers=test_user["headers"],
        )
        assert invite_response.status_code == 200
        invite_data = invite_response.json()
        assert invite_data["status"] == "invited"
        assert "member_id" in invite_data

        duplicate_response = await client.post(
            f"/api/workspaces/{test_workspace['id']}/members/invite",
            json={"email": second_user["email"], "role": "member"},
            headers=test_user["headers"],
        )
        assert duplicate_response.status_code == 400

        update_response = await client.patch(
            f"/api/workspaces/{test_workspace['id']}/members/{second_user['id']}",
            json={"role": "admin"},
            headers=test_user["headers"],
        )
        assert update_response.status_code == 200
        assert update_response.json()["status"] == "updated"

        remove_response = await client.delete(
            f"/api/workspaces/{test_workspace['id']}/members/{second_user['id']}",
            headers=test_user["headers"],
        )
        assert remove_response.status_code == 200
        assert remove_response.json()["status"] == "removed"

        remove_missing_response = await client.delete(
            f"/api/workspaces/{test_workspace['id']}/members/{second_user['id']}",
            headers=test_user["headers"],
        )
        assert remove_missing_response.status_code == 404


class TestWorkspaceInferenceServers:
    async def test_inference_server_crud(self, client, test_user, test_workspace):
        create_response = await client.post(
            f"/api/workspaces/{test_workspace['id']}/servers",
            json={
                "name": "Test Server",
                "type": "custom",
                "endpoint": "http://localhost:8010/",
                "description": "Test endpoint",
                "enabled": True,
                "api_key": "super-secret",
            },
            headers=test_user["headers"],
        )
        assert create_response.status_code == 200
        created_server = create_response.json()
        assert created_server["name"] == "Test Server"
        assert created_server["endpoint"] == "http://localhost:8010"
        server_id = created_server["id"]

        list_response = await client.get(
            f"/api/workspaces/{test_workspace['id']}/servers",
            headers=test_user["headers"],
        )
        assert list_response.status_code == 200
        listed_ids = [server["id"] for server in list_response.json()]
        assert server_id in listed_ids

        update_response = await client.patch(
            f"/api/workspaces/{test_workspace['id']}/servers/{server_id}",
            json={
                "endpoint": "http://localhost:8020/",
                "enabled": False,
                "api_key": "",
            },
            headers=test_user["headers"],
        )
        assert update_response.status_code == 200
        updated_server = update_response.json()
        assert updated_server["endpoint"] == "http://localhost:8020"
        assert updated_server["enabled"] is False
        assert updated_server["api_key"] is None

        delete_response = await client.delete(
            f"/api/workspaces/{test_workspace['id']}/servers/{server_id}",
            headers=test_user["headers"],
        )
        assert delete_response.status_code == 200
        assert delete_response.json()["status"] == "deleted"

        list_after_delete = await client.get(
            f"/api/workspaces/{test_workspace['id']}/servers",
            headers=test_user["headers"],
        )
        assert list_after_delete.status_code == 200
        listed_ids_after_delete = [server["id"] for server in list_after_delete.json()]
        assert server_id not in listed_ids_after_delete


class TestWorkspaceLogoUpload:
    async def test_upload_logo_updates_workspace(self, client, test_user, test_workspace):
        upload_response = await client.post(
            f"/api/workspaces/{test_workspace['id']}/upload-logo",
            files={"file": ("logo.png", b"fake-image-content", "image/png")},
            headers=test_user["headers"],
        )
        assert upload_response.status_code == 200
        payload = upload_response.json()
        assert payload["logo_url"].startswith("/uploads/logos/")
        assert payload["filename"].endswith(".png")

        workspace_response = await client.get(
            f"/api/workspaces/{test_workspace['id']}",
            headers=test_user["headers"],
        )
        assert workspace_response.status_code == 200
        workspace_data = workspace_response.json()
        assert workspace_data["logo_url"] == payload["logo_url"]

        Path("uploads/logos", payload["filename"]).unlink(missing_ok=True)


class TestWorkspaceFeatureFlags:
    async def test_workspace_payload_contains_role_and_feature_flags(
        self, client, test_user, test_workspace
    ):
        response = await client.get(
            f"/api/workspaces/{test_workspace['id']}",
            headers=test_user["headers"],
        )
        assert response.status_code == 200
        payload = response.json()

        assert payload["current_user_role"] in {"owner", "admin", "member", "viewer"}
        assert payload["feature_flags"] == {
            "chat": True,
            "files": True,
            "agents": True,
            "knowledge": True,
            "settings": True,
        }
