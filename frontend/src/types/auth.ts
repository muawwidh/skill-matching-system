export type Role = {
  name: string;
};

export type User = {
  id: string;
  email: string;
  full_name: string;
  status: string;
  roles: Role[];
};

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
};

export type LoginPayload = {
  email: string;
  password: string;
};

export type RegisterPayload = LoginPayload & {
  full_name: string;
};
