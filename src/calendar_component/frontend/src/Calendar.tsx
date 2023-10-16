import adaptivePlugin from "@fullcalendar/adaptive" // premium
import dayGridPlugin from "@fullcalendar/daygrid"
import interactionPlugin from "@fullcalendar/interaction"
import listPlugin from "@fullcalendar/list"
import multiMonthPlugin from "@fullcalendar/multimonth"
import resourceDayGridPlugin from "@fullcalendar/resource-daygrid" // premium
import resourceTimeGridPlugin from "@fullcalendar/resource-timegrid" // premium
import resourceTimelinePlugin from "@fullcalendar/resource-timeline" // premium
import timeGridPlugin from "@fullcalendar/timegrid"
import timelinePlugin from "@fullcalendar/timeline" // premium

import { EventClickArg } from "@fullcalendar/core"
import FullCalendar from "@fullcalendar/react"
import { ReactNode, createRef } from "react"
import {
  StreamlitComponentBase,
  withStreamlitConnection,
} from "streamlit-component-lib"
import styled from "styled-components"
import "./Calendar.css"

interface State {
  dateClick: any
  eventClick: any
  eventChange: any
  eventsSet: any
}

const FullCalendarWrapper = styled.div<{ $customCSS?: string }>`
  ${(props) => props.$customCSS}
`
class Calendar extends StreamlitComponentBase<State> {
  calendarRef = createRef<HTMLDivElement>();

  scrollToCurrentTime = () => {
    const currentDate = new Date();
    const formattedDay = currentDate.toISOString().split('T')[0];

    if (!this.calendarRef.current) return
    const dayElement = (this.calendarRef.current as HTMLElement).querySelector(`[data-date="${formattedDay}"]`);

    if (dayElement) {
      dayElement.scrollIntoView();
    }
  }

  componentDidMount() {
    super.componentDidMount?.();
    // console.log(this.calendarRef.current)
    this.scrollToCurrentTime();
  }

  public render = (): ReactNode => {
    const events = this.props.args["events"]
    const options = this.props.args["options"]
    const customCSS = this.props.args["custom_css"]
    const licenseKey = this.props.args["license_key"]

    const plugins = [
      adaptivePlugin,
      dayGridPlugin,
      interactionPlugin,
      listPlugin,
      multiMonthPlugin,
      resourceDayGridPlugin,
      resourceTimeGridPlugin,
      resourceTimelinePlugin,
      timeGridPlugin,
      timelinePlugin,
    ]

    return (
      <FullCalendarWrapper $customCSS={customCSS} ref={this.calendarRef}>
        <FullCalendar
          plugins={plugins}
          initialEvents={events}
          schedulerLicenseKey={licenseKey}
          eventClick={this.handleEventClick}
          eventContent={this.eventContent}
          {...options}
        />
      </FullCalendarWrapper>
    )
  }

  private eventContent = (arg: any) => {
    return <div>
      <a target="_blank" rel="noreferrer" href={arg.event.url}>
        {arg.event.title}
      </a>

      <span style={{float: "right"}}>
        {arg.event.extendedProps.going &&
          <span>({arg.event.extendedProps.going})&nbsp;</span>}
        {arg.event.extendedProps.source}
      </span>
    </div>
  }

  private handleEventClick = (arg: EventClickArg) => {
    arg.jsEvent.preventDefault()
    window.open(arg.event.url, "_blank");
  }
}

export default withStreamlitConnection(Calendar)
