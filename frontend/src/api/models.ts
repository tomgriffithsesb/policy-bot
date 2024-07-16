export type AskResponse = {
    answer: string;
    citations: Citation[];
    error?: string;
    message_id?: string;
    feedback?: Feedback;
};

export type Citation = {
    part_index?: number;
    content: string;
    id: string;
    title: string | null;
    filepath: string | null;
    url: string | null;
    metadata: string | null;
    chunk_id: string | null;
    reindex_id: string | null;
    page: string | null;
}

export type ToolMessageContent = {
    citations: Citation[];
    intent: string;
}

export type ChatMessage = {
    id: string;
    role: string;
    content: string;
    end_turn?: boolean;
    date: string;
    feedback?: Feedback;
    context?: string;
    filter?: string[];
};

export type Conversation = {
    id: string;
    title: string;
    messages: ChatMessage[];
    date: string;
}

export enum ChatCompletionType {
    ChatCompletion = "chat.completion",
    ChatCompletionChunk = "chat.completion.chunk"
}

export type ChatResponseChoice = {
    messages: ChatMessage[];
}

export type ChatResponse = {
    id: string;
    model: string;
    created: number;
    object: ChatCompletionType;
    choices: ChatResponseChoice[];
    history_metadata: {
        conversation_id: string;
        title: string;
        date: string;
    }
    error?: any;
}

export type ConversationRequest = {
    messages: ChatMessage[];
};

export type UserInfo = {
    access_token: string;
    expires_on: string;
    id_token: string;
    provider_name: string;
    user_claims: any[];
    user_id: string;
};

export enum CosmosDBStatus {
    NotConfigured = "CosmosDB is not configured",
    NotWorking = "CosmosDB is not working",
    InvalidCredentials = "CosmosDB has invalid credentials",
    InvalidDatabase = "Invalid CosmosDB database name",
    InvalidContainer = "Invalid CosmosDB container name",
    Working = "CosmosDB is configured and working",
}

export type CosmosDBHealth = {
    cosmosDB: boolean,
    status: string
}

export enum ChatHistoryLoadingState {
    Loading = "loading",
    Success = "success",
    Fail = "fail",
    NotStarted = "notStarted"
}

export type ErrorMessage = {
    title: string,
    subtitle: string
}

export type UI = {
    title: string;
    chat_title: string;
    chat_description: string;
    logo?: string;
    chat_logo?: string;
    show_share_button?: boolean
}

export type FrontendSettings = {
    auth_enabled?: string | null;
    feedback_enabled?: string | null;
    ui?: UI;
    sanitize_answer?: boolean;
}

export enum Feedback {
    Neutral = "neutral",
    Positive = "positive",
    Negative = "negative",
    DifficultToUnderstand = "difficult_to_understand",
    NotInformative = "not_informative",
    IncorrectInformation = "incorrect_information",
    DidntGetAnswer = "didnt_get_answer",
    OtherUnhelpful = "other_unhelpful",
    HateSpeech = "hate_speech",
    Violent = "violent",
    Sexual = "sexual",
    Manipulative = "manipulative",
    OtherHarmful = "other_harmful"
}
