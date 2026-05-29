from elevenlabs import ElevenLabs
client = ElevenLabs()
client.service_accounts.api_keys.create(
    service_account_user_id="service_account_user_id",
    name="string",
    permissions=[
        "text_to_speech"
    ],
)

