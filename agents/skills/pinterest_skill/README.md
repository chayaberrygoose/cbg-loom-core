# [SKILL]: PINTEREST_UPLINK
// STATUS: IN_DEVELOPMENT
// VERSION: 1.0

## [NARRATIVE]
This skill enables the Specialist to transmit Specimens (products/images) to the Pinterest Archive. 

## [ESTABLISHING_CONDUIT]
1.  **Pinterest Developer Portal**: Create an application at [Pinterest Developers](https://developers.pinterest.com/apps/).
2.  **Redirect URI**: Set `https://localhost/` (or your preferred URI) as the redirect URI in the app settings.
3.  **The Archive (.env)**: Add the following keys to your `.env` file:
    ```env
    PINTEREST_CLIENT_ID=your_client_id
    PINTEREST_CLIENT_SECRET=your_client_secret
    PINTEREST_REDIRECT_URI=https://localhost/
    ```
4.  **Ritual of Initiation**:
    - Run the auth script to get the login link:
      `python scripts/pinterest_auth.py`
    - Navigate to the URL, authorize, and copy the `code` from the redirect URL.
    - Exchange the code for an access token:
      `python scripts/pinterest_auth.py --code YOUR_CODE_HERE`
    - Copy the resulting `PINTEREST_ACCESS_TOKEN` into your `.env`.

## [FUNCTIONS]
- `get_account_info()`: Verifies connection.
- `create_board()`: (Pending Implementation)
- `create_pin()`: (Pending Implementation)
