import { createContext, useContext } from "react";

const NameContext = createContext<string>("You");
export const useParticipantName = () => useContext(NameContext);
export const ParticipantNameProvider = NameContext.Provider;
